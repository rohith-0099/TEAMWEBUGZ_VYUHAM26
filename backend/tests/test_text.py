"""Tests for text normalization and defanging. Owner: Backend Core."""
from app.utils.text import defang, normalize_text


def test_normalize_line_endings():
    raw = "Line 1\r\nLine 2\rLine 3\nLine 4"
    assert normalize_text(raw) == "Line 1\nLine 2\nLine 3\nLine 4"


def test_normalize_smart_quotes_and_dashes():
    raw = "‘single’ and “double” quotes — em-dash – en-dash − minus"
    expected = "'single' and \"double\" quotes - em-dash - en-dash - minus"
    assert normalize_text(raw) == expected


def test_normalize_non_breaking_spaces_and_tabs():
    raw = "Hello\u00a0World\twith    multiple   spaces  "
    assert normalize_text(raw) == "Hello World with multiple spaces"


def test_normalize_zero_width_removal():
    raw = "Hidden\u200bzero\u200cwidth\u200dcharacters\u2060and\ufeffBOM"
    assert normalize_text(raw) == "HiddenzerowidthcharactersandBOM"


def test_normalize_excess_newlines_collapse():
    raw = "Para 1\n\n\n\n\nPara 2\n\nPara 3\n\n\n"
    assert normalize_text(raw) == "Para 1\n\nPara 2\n\nPara 3"


def test_normalize_empty_and_whitespace():
    assert normalize_text("") == ""
    assert normalize_text("   \n\n\t   ") == ""


def test_defang_ipv4():
    assert defang("1.2.3.4", "ipv4") == "1[.]2[.]3[.]4"
    assert defang("192.168.1.1", "ipv4") == "192[.]168[.]1[.]1"


def test_defang_ipv6():
    assert defang("2001:db8::1", "ipv6") == "2001[:]db8[:][:]1"
    assert defang("fe80::1ff:fe23:4567:890a", "ipv6") == "fe80[:][:]1ff[:]fe23[:]4567[:]890a"


def test_defang_domain():
    assert defang("evil.com", "domain") == "evil[.]com"
    assert defang("sub.evil.co.uk", "domain") == "sub[.]evil[.]co[.]uk"


def test_defang_url():
    assert defang("http://evil.com/gate.php", "url") == "hxxp://evil[.]com/gate.php"
    assert defang("https://sub.evil.com/path/file.exe?q=1.2", "url") == "hxxps://sub[.]evil[.]com/path/file.exe?q=1.2"
    assert defang("ftp://files.evil.com/dl", "url") == "fxp://files[.]evil[.]com/dl"


def test_defang_email():
    assert defang("attacker@evil.com", "email") == "attacker[@]evil[.]com"
    assert defang("first.last@malicious.co.uk", "email") == "first.last[@]malicious[.]co[.]uk"


def test_defang_unchanged_types():
    # Hashes, CVE, paths, registry, btc should be untouched
    md5 = "d41d8cd98f00b204e9800998ecf8427e"
    sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    cve = "CVE-2026-12345"
    path = "C:\\Windows\\System32\\cmd.exe"
    reg = "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
    btc = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

    assert defang(md5, "md5") == md5
    assert defang(sha256, "sha256") == sha256
    assert defang(cve, "cve") == cve
    assert defang(path, "filepath") == path
    assert defang(reg, "registry") == reg
    assert defang(btc, "btc") == btc
