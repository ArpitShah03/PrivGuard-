import re
from typing import List, Dict, Any, Optional, Set
from models.schemas import PIIFinding, DocumentBlock

# List of common surnames where identical names alone must NEVER be merged without corroborating evidence
COMMON_SURNAMES = {
    "smith", "johnson", "williams", "brown", "jones", "garcia", "miller", "davis",
    "rodriguez", "martinez", "hernandez", "lopez", "gonzalez", "wilson", "anderson",
    "thomas", "taylor", "moore", "jackson", "martin", "lee", "perez", "thompson",
    "white", "harris", "sanchez", "clark", "ramirez", "lewis", "robinson", "walker",
    "young", "allen", "king", "wright", "scott", "torres", "nguyen", "hill", "flores",
    "green", "adams", "nelson", "baker", "hall", "rivera", "campbell", "mitchell",
    "carter", "roberts", "patel", "shah", "kumar", "singh"
}


def normalize_name(name: str) -> str:
    """Strip honorifics, titles, and extra whitespace for clean name comparison."""
    clean = re.sub(r'(?i)\b(mr|ms|mrs|dr|prof|director|vp|head|officer|exec|ciso|ceo|cfo|cto)\.?\b', '', name)
    return " ".join(clean.strip().lower().split())


def is_common_surname(name: str) -> bool:
    """Check if the surname belongs to the common surnames list."""
    parts = normalize_name(name).split()
    if parts and parts[-1] in COMMON_SURNAMES:
        return True
    return False


def is_name_variant(name1: str, name2: str) -> bool:
    """
    Check if name1 and name2 could structurally be variants of the same person:
    - Initial match: 'T. Lindqvist' vs 'Tobias Lindqvist', 'S. Connor' vs 'Sarah Connor'
    - Single typo on long surname (edit distance <= 2): 'Tobias Lindevist' vs 'Tobias Lindqvist'
    """
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)
    if not n1 or not n2 or n1 == n2:
        return False

    parts1 = n1.split()
    parts2 = n2.split()

    if len(parts1) == 2 and len(parts2) == 2:
        first1, last1 = parts1[0].replace('.', ''), parts1[1]
        first2, last2 = parts2[0].replace('.', ''), parts2[1]

        # Case 1: Matching surname and initial (e.g. 't' and 'tobias', last1 == last2)
        if last1 == last2 and (first1[0] == first2[0]) and (len(first1) == 1 or len(first2) == 1):
            return True

        # Case 2: Matching first name and minor surname distance
        if first1 == first2 and len(last1) >= 6 and len(last2) >= 6:
            diff = sum(c1 != c2 for c1, c2 in zip(last1, last2)) + abs(len(last1) - len(last2))
            if diff <= 2:
                return True

    return False


class ResolvedEntity:
    def __init__(self, entity_id: str, pii_type: str, primary_text: str, token: Optional[str] = None):
        self.entity_id = entity_id
        self.pii_type = pii_type
        self.primary_text = primary_text
        self.token = token
        self.variants: Set[str] = {primary_text.lower()}
        self.emails: Set[str] = set()
        self.employee_ids: Set[str] = set()
        self.phones: Set[str] = set()
        self.roles: Set[str] = set()

    def add_mention(self, text: str):
        self.variants.add(text.lower())
        if len(text) > len(self.primary_text):
            self.primary_text = text


class EntityRegistry:
    """
    Batch-scoped or session-scoped entity registry to assign deterministic,
    stable semantic replacement tokens ([PERSON_017], [EMPID_004], etc.).
    """
    def __init__(self):
        self.entities: Dict[str, ResolvedEntity] = {}
        self.type_counters: Dict[str, int] = {}
        self.text_to_entity: Dict[tuple, str] = {}
        self.alias_map: Dict[str, str] = {}

    def get_or_create_token(self, pii_type: str, text: str) -> str:
        key = (pii_type, text.lower())
        if key in self.text_to_entity:
            entity_id = self.text_to_entity[key]
            # Resolve alias if merged
            root_id = self.get_root_id(entity_id)
            return self.entities[root_id].token

        curr = self.type_counters.get(pii_type, 0) + 1
        self.type_counters[pii_type] = curr
        token = f"[{pii_type}_{curr:03d}]"
        entity_id = f"ent_{pii_type.lower()}_{curr:03d}"

        entity = ResolvedEntity(entity_id=entity_id, pii_type=pii_type, primary_text=text, token=token)
        self.entities[entity_id] = entity
        self.text_to_entity[key] = entity_id
        return token

    def get_root_id(self, entity_id: str) -> str:
        curr = entity_id
        while curr in self.alias_map:
            curr = self.alias_map[curr]
        return curr

    def link_entities(self, target_entity_id: str, source_entity_id: str):
        """Merge source entity into target entity, updating alias maps."""
        root_target = self.get_root_id(target_entity_id)
        root_source = self.get_root_id(source_entity_id)
        if root_target == root_source:
            return

        target = self.entities[root_target]
        source = self.entities.pop(root_source, None)
        self.alias_map[root_source] = root_target

        if source:
            if not target.token and source.token:
                target.token = source.token
            target.variants.update(source.variants)
            target.emails.update(source.emails)
            target.employee_ids.update(source.employee_ids)
            target.phones.update(source.phones)
            target.roles.update(source.roles)
            if len(source.primary_text) > len(target.primary_text):
                target.primary_text = source.primary_text

            for var in source.variants:
                self.text_to_entity[(target.pii_type, var)] = root_target


class EntityResolver:
    """
    Evidence-backed entity resolution engine.
    Ensures name similarity alone is NEVER enough to merge identities.
    Requires corroborating evidence: matching email, employee ID, or phone.
    Enforces strict conflict prevention (conflicting IDs/emails prevent merging).
    """
    def __init__(self, registry: Optional[EntityRegistry] = None):
        self.registry = registry or EntityRegistry()

    def _check_conflict(self, e1: ResolvedEntity, e2: ResolvedEntity) -> bool:
        """Conflicting explicit identity attributes MUST strictly prevent merging."""
        if e1.employee_ids and e2.employee_ids and e1.employee_ids.isdisjoint(e2.employee_ids):
            return True
        if e1.emails and e2.emails and e1.emails.isdisjoint(e2.emails):
            return True
        if e1.phones and e2.phones and e1.phones.isdisjoint(e2.phones):
            return True
        return False

    def _check_corroborating_evidence(self, e1: ResolvedEntity, e2: ResolvedEntity) -> Optional[Dict[str, Any]]:
        """Check for positive corroborating evidence between two candidates."""
        shared_emails = e1.emails.intersection(e2.emails)
        if shared_emails:
            return {"shared_email": list(shared_emails)[0]}

        shared_empids = e1.employee_ids.intersection(e2.employee_ids)
        if shared_empids:
            return {"shared_empid": list(shared_empids)[0]}

        shared_phones = e1.phones.intersection(e2.phones)
        if shared_phones:
            return {"shared_phone": list(shared_phones)[0]}

        # Check email handle match across attached emails
        all_emails = e1.emails.union(e2.emails)
        for em in all_emails:
            clean_handle = re.sub(r'[^a-z0-9]', '', em.split('@')[0].lower())
            n1_alpha = re.sub(r'[^a-z0-9]', '', normalize_name(e1.primary_text))
            n2_alpha = re.sub(r'[^a-z0-9]', '', normalize_name(e2.primary_text))
            if clean_handle == n1_alpha or clean_handle == n2_alpha:
                return {"handle_match": em}
            parts1 = normalize_name(e1.primary_text).split()
            parts2 = normalize_name(e2.primary_text).split()
            if len(parts1) >= 2 and (parts1[0][0] + parts1[-1] == clean_handle):
                return {"handle_match": em}
            if len(parts2) >= 2 and (parts2[0][0] + parts2[-1] == clean_handle):
                return {"handle_match": em}

        return None

    def _can_merge_persons(self, e1: ResolvedEntity, e2: ResolvedEntity) -> tuple[bool, Optional[Dict[str, Any]]]:
        """
        Conservative merging policy:
        - Conflicting evidence -> NEVER merge
        - Variant name -> requires corroborating evidence
        - Exact same name:
            - Common surname -> requires corroborating evidence
            - Uncommon surname -> merges if no conflicting evidence
        """
        if self._check_conflict(e1, e2):
            return False, None

        n1 = normalize_name(e1.primary_text)
        n2 = normalize_name(e2.primary_text)
        corrob = self._check_corroborating_evidence(e1, e2)

        # Case 1: Variant names (initials, minor distance)
        if is_name_variant(e1.primary_text, e2.primary_text):
            if corrob:
                return True, corrob
            # Name similarity alone is NEVER enough to merge
            return False, None

        # Case 2: Exact same name
        if n1 == n2:
            if is_common_surname(e1.primary_text):
                if corrob:
                    return True, corrob
                # Common surname with no corroborating evidence -> separate identities
                return False, None
            else:
                # Distinct/uncommon surname with no conflict
                return True, corrob or {"exact_name_match_uncommon": True}

        return False, None

    def resolve_findings(
        self,
        findings: List[PIIFinding],
        blocks: Optional[List[DocumentBlock]] = None
    ) -> List[PIIFinding]:
        """
        Perform evidence-backed entity resolution across findings in a document/batch.
        Enriches findings with entity_id and replacement_token.
        """
        # Step 1: Extract block-level co-occurrence context
        block_context_map: Dict[str, Dict[str, Set[str]]] = {}
        if blocks:
            for b in blocks:
                block_context_map[b.location] = {
                    "emails": set(),
                    "employee_ids": set(),
                    "phones": set(),
                    "names": set()
                }

            for f in findings:
                if f.location in block_context_map:
                    ctx = block_context_map[f.location]
                    if f.pii_type == "EMAIL":
                        ctx["emails"].add(f.text.lower())
                    elif f.pii_type in ["EMPLOYEE_ID", "GOVERNMENT_ID"]:
                        ctx["employee_ids"].add(f.text.upper())
                    elif f.pii_type == "PHONE":
                        ctx["phones"].add("".join(c for c in f.text if c.isdigit()))
                    elif f.pii_type == "PERSON":
                        ctx["names"].add(f.text)

        # Step 2: Handle Non-PERSON findings (deterministic tokens by exact value)
        for f in findings:
            if f.pii_type != "PERSON":
                token = self.registry.get_or_create_token(f.pii_type, f.text)
                f.replacement_token = token
                root_id = self.registry.get_root_id(self.registry.text_to_entity.get((f.pii_type, f.text.lower()), ""))
                f.entity_id = root_id

        # Step 3: Handle PERSON findings with conservative candidate instantiation
        person_findings = [f for f in findings if f.pii_type == "PERSON"]
        candidate_entities: List[ResolvedEntity] = []

        for i, f in enumerate(person_findings):
            cand_id = f"cand_person_{len(self.registry.entities) + i + 1:04d}"
            cand = ResolvedEntity(entity_id=cand_id, pii_type="PERSON", primary_text=f.text)
            if f.location in block_context_map:
                ctx = block_context_map[f.location]
                cand.emails.update(ctx["emails"])
                cand.employee_ids.update(ctx["employee_ids"])
                cand.phones.update(ctx["phones"])
            candidate_entities.append(cand)
            self.registry.entities[cand_id] = cand

        # Step 4: Conservative merge evaluation against existing registry entities and other candidates
        for cand in candidate_entities:
            cand_root = self.registry.get_root_id(cand.entity_id)
            cand_ent = self.registry.entities.get(cand_root)
            if not cand_ent:
                continue

            for existing_id, existing_ent in list(self.registry.entities.items()):
                existing_root = self.registry.get_root_id(existing_id)
                if cand_root == existing_root or existing_ent.pii_type != "PERSON":
                    continue

                can_merge, evidence_details = self._can_merge_persons(existing_ent, cand_ent)
                if can_merge:
                    target_root = existing_root if existing_ent.token else cand_root
                    source_root = cand_root if target_root == existing_root else existing_root
                    self.registry.link_entities(target_root, source_root)
                    target_ent = self.registry.entities.get(target_root)
                    if target_ent:
                        if not hasattr(target_ent, "evidence_log"):
                            target_ent.evidence_log = []
                        target_ent.evidence_log.append({
                            "merged_variant": cand_ent.primary_text if target_root == existing_root else existing_ent.primary_text,
                            "evidence": evidence_details
                        })
                    cand_root = target_root
                    cand_ent = target_ent
                    break

        # Step 5: Assign clean sequential tokens to distinct root PERSON entities
        for cand in candidate_entities:
            root_id = self.registry.get_root_id(cand.entity_id)
            root_ent = self.registry.entities.get(root_id)
            if root_ent and not root_ent.token:
                curr = self.registry.type_counters.get("PERSON", 0) + 1
                self.registry.type_counters["PERSON"] = curr
                root_ent.token = f"[PERSON_{curr:03d}]"

        # Step 6: Map tokens and evidence back to PERSON findings
        for f, cand in zip(person_findings, candidate_entities):
            root_id = self.registry.get_root_id(cand.entity_id)
            root_ent = self.registry.entities.get(root_id)
            if root_ent:
                f.entity_id = root_id
                f.replacement_token = root_ent.token
                if hasattr(root_ent, "evidence_log") and root_ent.evidence_log:
                    f.evidence = root_ent.evidence_log[0]
                else:
                    f.evidence = {"status": "unmerged_distinct_entity"}

        return findings


# Shared registry instance
default_entity_registry = EntityRegistry()
default_entity_resolver = EntityResolver(default_entity_registry)
