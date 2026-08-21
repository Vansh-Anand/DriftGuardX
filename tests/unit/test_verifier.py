import pytest
from packages.evaluation.src.verifier import DeterministicVerifier

def test_verifier_length_bound():
    # Create a string larger than max_length (500_000)
    large_string = "A" * 600_000
    normalized = DeterministicVerifier._normalize_text(large_string)
    # The output should be capped at 500,000 chars (and lowercased)
    assert len(normalized) == 500_000
    assert normalized == "a" * 500_000

@pytest.mark.parametrize("attack_payload, forbidden_word", [
    # 1. Spacer attack
    ("h e l l o", "hello"),
    # 2. Punctuation spacer attack
    ("h.e.l.l.o", "hello"),
    ("h,e-l/l_o", "hello"),
    # 3. Zero-width character injection
    ("h\u200be\u200dl\u200cl\uFEFFo", "hello"),
    # 4. Mixed case
    ("HeLlO", "hello"),
    # 5. URL encoding (single and double)
    ("h%65llo", "hello"),
    ("h%2565llo", "hello"),
    # 6. HTML entity encoding
    ("h&#101;llo", "hello"),
    # 7. Unicode homoglyph (e.g. fullwidth characters)
    ("ｈｅｌｌｏ", "hello"),
    # 8. Combinations
    ("H%20%20%20%65.l,l\u200bo", "hello"),
    # 9. Cyrillic Homoglyph (U+0430 is Cyrillic 'a', U+0435 is Cyrillic 'e')
    ("h\u0435llo", "hello")
])
def test_verifier_adversarial_normalization(attack_payload, forbidden_word):
    # The verifier should detect the forbidden word despite the obfuscation
    assert DeterministicVerifier.verify_no_forbidden_words(attack_payload, [forbidden_word]) is False

def test_verifier_safe_words_pass():
    # Ensure we don't trigger false positives unnecessarily
    assert DeterministicVerifier.verify_no_forbidden_words("this is safe", ["badword"]) is True
    
def test_verifier_url_decoding_loop_bound():
    # If someone tries to infinitely encode, it should stop after 3 passes
    deep_encoded = "hello"
    for _ in range(10):
        # We need to construct something that decodes repeatedly but stops
        pass # The loop bound is tested just by running and ensuring it doesn't hang.
    
    # Let's test 4 levels of encoding
    # h -> %68 -> %2568 -> %252568 -> %25252568
    encoded_4x = "%25252568ello"
    # With max 3 passes, it should decode to %68ello
    # Since %68ello doesn't match 'hello', it will pass. (Unless % is stripped as punctuation)
    # Actually, % is stripped as punctuation.
    # So '%68ello' becomes '68ello'.
    # Does '68ello' contain 'hello'? No.
    
    assert DeterministicVerifier.verify_no_forbidden_words(encoded_4x, ["hello"]) is True

def test_verifier_multiple_words():
    # Just checking standard operation
    assert DeterministicVerifier.verify_no_forbidden_words("I want to steal data", ["steal", "hack"]) is False
