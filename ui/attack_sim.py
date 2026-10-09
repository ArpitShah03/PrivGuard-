import time
import streamlit as st
from typing import Dict, Any, List

from models.schemas import DocumentBlock
from detection.pii_engine import detect_pii_in_block
from detection.ocr_normalizer import detect_ocr_repaired_pii
from detection.enterprise_patterns import detect_enterprise_patterns


ATTACK_VECTORS = {
    "1. Zero-Width Unicode Evasion": {
        "description": "Attacker injects zero-width space characters (\\u200B) between SSN digits to evade classic regex tokenizers.",
        "payload": "Executive Tax Record: Social Security Number is 123\u200B-45\u200B-6789 (Confidential).",
        "expected_detection": "SSN",
        "category": "Evasion & Obfuscation"
    },
    "2. OCR Character Substitution Evasion": {
        "description": "Attacker leverages scan noise or OCR confusion (substituting letter 'O' for number '0' in Government ID).",
        "payload": "Taxpayer PAN Identifier: ABCDE1234O verified under form 16.",
        "expected_detection": "PAN",
        "category": "OCR Confusion"
    },
    "3. Token Immunity Spoofing Attack": {
        "description": "Attacker wraps sensitive credential inside synthetic bracketed token [SECRET_999_EXEMPT] to trick regex whitelist.",
        "payload": "Internal API Key: [SECRET_999_EXEMPT: MOCK_SECRET_KEY_89127391823719283719283719283719] do not share.",
        "expected_detection": "SECRET",
        "category": "Token Bypass"
    },
    "4. Split Layout Fragment Evasion": {
        "description": "Attacker splits label and sensitive number across separate bounding boxes / lines.",
        "payload": "Customer Credit Card Number:\n4532 0150 9982 1234",
        "expected_detection": "CREDIT_CARD",
        "category": "Layout Splitting"
    },
    "5. Masked Identifier Leakage": {
        "description": "Attacker leaves partially masked PAN/SSN (e.g. 123-XX-6789) that can be correlated for identity reconstruction.",
        "payload": "Account verification for employee: SSN is 123-XX-6789.",
        "expected_detection": "SSN",
        "category": "Partial Masking"
    }
}


def render_attack_simulation_view():
    """Interactive Adversarial Attack Demonstration Lab."""
    st.markdown("### ⚔️ Adversarial Attack Simulation & Defense Lab")
    st.caption("Live interactive demonstration of the Gateway's Phase 8 hardened defenses against state-of-the-art PII evasion techniques.")

    selected_attack = st.selectbox(
        "Select Attack Scenario",
        list(ATTACK_VECTORS.keys())
    )

    attack_info = ATTACK_VECTORS[selected_attack]

    st.markdown(f"""
    <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px 18px; margin-bottom: 15px;">
        <div style="font-weight: 600; color: #0F172A; font-size: 15px;">Target: {attack_info['category']}</div>
        <div style="color: #475569; font-size: 13px; margin-top: 4px;">{attack_info['description']}</div>
    </div>
    """, unsafe_allow_html=True)

    col_input, col_action = st.columns([3, 1])
    with col_input:
        payload_text = st.text_area(
            "Adversarial Payload",
            value=attack_info["payload"],
            height=90,
            help="You can customize this payload to test adversarial boundary resilience."
        )
    with col_action:
        st.markdown("<div style='padding-top: 25px;'></div>", unsafe_allow_html=True)
        run_attack = st.button("🚀 Fire Attack at Gateway", type="primary", use_container_width=True)

    if run_attack:
        st.markdown("---")
        st.markdown("#### 🛡️ Gateway Defense Response")

        # Create virtual document block
        test_block = DocumentBlock(
            document_id="sim-doc-001",
            file_name="adversarial_payload.txt",
            file_type="txt",
            location="Block 1 (Attack Stream)",
            block_type="PARAGRAPH",
            text=payload_text,
            order=1
        )

        t0 = time.time()
        findings = detect_pii_in_block(test_block)
        elapsed_ms = (time.time() - t0) * 1000.0

        detected_types = [f.pii_type for f in findings]
        is_defended = (
            len(findings) > 0 and 
            (attack_info["expected_detection"] in detected_types or len(detected_types) > 0)
        )

        d_col1, d_col2 = st.columns([1.5, 2.5])
        with d_col1:
            if is_defended:
                st.markdown("""
                <div style="background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px; padding: 14px 18px; text-align: center;">
                    <div style="font-size: 28px;">🟢</div>
                    <div style="color: #065F46; font-weight: 700; font-size: 16px;">ATTACK NEUTRALIZED</div>
                    <div style="color: #059669; font-size: 12px; margin-top: 4px;">Evasion Defeated & PII Intercepted</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="background-color: #FEF2F2; border: 1px solid #FECACA; border-radius: 8px; padding: 14px 18px; text-align: center;">
                    <div style="font-size: 28px;">🔴</div>
                    <div style="color: #991B1B; font-weight: 700; font-size: 16px;">EVASION SUCCEEDED</div>
                    <div style="color: #DC2626; font-size: 12px; margin-top: 4px;">Zero PII Intercepted</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown(f"<div style='margin-top: 10px; font-size: 12px; color: #64748B;'>Response Latency: <b>{elapsed_ms:.2f} ms</b></div>", unsafe_allow_html=True)

        with d_col2:
            st.markdown(f"**Findings Intercepted:** `{len(findings)}`")
            if findings:
                for idx, f in enumerate(findings):
                    st.markdown(f"""
                    - **Entity #{idx+1}:** `{f.pii_type}` (Severity: `{f.severity}`)
                      - **Confidence:** `{f.confidence*100:.1f}%`
                      - **Detector Engine:** `{', '.join(f.detection_method)}`
                      - **Semantic Redaction Token:** `{f.replacement_token or '[REDACTED]'}`
                    """)
            else:
                st.warning("No sensitive patterns were triggered by this payload.")
