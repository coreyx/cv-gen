"""Tests for the web adapter: profile evaluation, JSON-LD, fetching (REQ-4)."""

import shutil
import sys
from pathlib import Path

import pytest

from cv_gen.adapters import AdapterContext
from cv_gen.adapters.web import WebAdapter, WebOptions
from cv_gen.adapters.web.engine import evaluate, parse_html, set_path
from cv_gen.adapters.web.jsonld import person_to_basics, profile_from_url
from cv_gen.adapters.web.profile import FieldSpec, load_profile
from cv_gen.errors import CvGenError
from cv_gen.fetch import decode, fetch_bytes, is_loopback, read_text

ROOT = Path(__file__).parent.parent
PAGE = ROOT / "tests" / "fixtures" / "web" / "about.html"
PROFILE = ROOT / "examples" / "profiles" / "generic-about.yaml"
PLUGINS = Path(__file__).parent / "plugins"


def run(tmp_path: Path, profile_text: str, page: Path = PAGE, **options):
    """Run the web adapter with an inline profile against a saved page."""
    profile = tmp_path / "profile.yaml"
    profile.write_text(profile_text, encoding="utf-8")
    opts = WebOptions(profile=profile, path=page, **options)
    return WebAdapter().extract(opts, AdapterContext(base_dir=tmp_path))


def test_generic_profile_extracts_expected_model() -> None:
    """AC 4.1: the fixture page extracts to the expected model with only a YAML profile."""
    options = WebOptions(profile=PROFILE, path=PAGE)
    resume = WebAdapter().extract(options, AdapterContext(base_dir=ROOT))
    data = resume.to_data()
    assert data["basics"] == {
        "name": "Jordan Lee",
        "label": "Staff Engineer",
        "headline": "I make slow systems fast.",
        "email": "jordan@example.com",
        "summary": "Fifteen years of performance engineering, from game engines to databases.",
        "location": {"city": "Lisbon", "countryCode": "PT"},
        "profiles": [
            {
                "network": "GitHub",
                "username": "jordanlee-example",
                "url": "https://github.com/jordanlee-example",
            },
            {
                "network": "Mastodon",
                "username": "jordanlee",
                "url": "https://mastodon.social/@jordanlee",
            },
        ],
    }
    assert data["work"] == [
        {
            "name": "Fastly",
            "position": "Staff Engineer",
            "startDate": "2021",
            "summary": "Edge runtime and WebAssembly performance.",
            "tags": ["employee"],
        },
        {
            "name": "Hotpath Labs",
            "position": "Founder",
            "startDate": "2016",
            "endDate": "2020",
            "summary": "A profiler for game studios, sold in 2020.",
            "tags": ["founder"],
        },
        {
            "name": "Ubisoft",
            "startDate": "2009",
            "endDate": "2016",
            "periods": [
                {"startDate": "2009", "endDate": "2012"},
                {"startDate": "2014", "endDate": "2016"},
            ],
            "summary": "Engine programmer on rendering and streaming, across two stints.",
            "tags": ["employee"],
        },
    ]
    assert data["skills"] == [
        {"name": "Languages", "keywords": ["C++", "Rust", "Python"]},
        {"name": "Tools", "keywords": ["perf", "Tracy"]},
    ]
    assert data["sections"] == [
        {
            "id": "now",
            "title": "Now",
            "items": [
                {"title": "Fastly", "text": "Leading the edge-compute runtime team."},
                {"title": "Open source", "text": "Maintaining two profiling tools."},
            ],
        },
        {
            "id": "story",
            "title": "How I got here",
            "paragraphs": [
                "I started by modding games.",
                "Then I wrote the first profiler I could not live without.",
            ],
        },
    ]


def test_exclude_removes_responsive_duplicates(tmp_path: Path) -> None:
    """AC 4.3: excluded elements never reach any field."""
    profile = "exclude: ['.mobile-only']\nfields:\n  basics.summary: {selector: '.job .desc'}\n"
    assert run(tmp_path, profile).basics.summary == (
        "Staff Engineer. Edge runtime and WebAssembly performance."
    )
    without = "fields:\n  basics.summary: {selector: '.job .desc'}\n"
    assert (run(tmp_path, without).basics.summary or "").endswith("Staff Engineer. Edge runtime.")


def test_jsonld_baseline_alone(tmp_path: Path) -> None:
    """AC 4.4: with no basics fields, JSON-LD supplies name, label, location and profiles."""
    basics = run(tmp_path, "fields: {}\n").basics
    assert basics.name == "Jordan Lee"
    assert basics.label == "Staff Engineer"
    assert basics.location is not None and basics.location.city == "Lisbon"
    assert [p.network for p in basics.profiles] == ["GitHub", "LinkedIn"]
    assert basics.profiles[1].username == "jordanlee-example"


def test_jsonld_can_be_turned_off(tmp_path: Path) -> None:
    """A profile can ignore the page's JSON-LD."""
    assert run(tmp_path, "jsonld: false\n").basics.name is None


def test_module_transform_applies_to_field(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC 4.5: a profile's transforms module supplies a transform its fields use."""
    monkeypatch.setattr(sys, "path", [str(PLUGINS), *sys.path])
    profile = (
        "transforms_module: sample_transforms\n"
        "fields:\n  basics.label: {selector: '#now h2', transforms: [shout]}\n"
    )
    assert run(tmp_path, profile).basics.label == "NOW!"


def test_required_selector_names_field(tmp_path: Path) -> None:
    """AC 4.6 (selector half): a required selector that matches nothing names the field."""
    profile = (
        "fields:\n  work:\n    each: '.job'\n"
        "    fields:\n      name: {selector: '.nope', required: true}\n"
    )
    with pytest.raises(CvGenError, match=r"work\[0\]\.name: required selector '\.nope'"):
        run(tmp_path, profile)
    each = "fields:\n  work: {each: '.none', required: true, fields: {name: {}}}\n"
    with pytest.raises(CvGenError, match=r"work: required selector '\.none'"):
        run(tmp_path, each)


def test_optional_selector_leaves_field_empty(tmp_path: Path) -> None:
    """An optional selector that matches nothing leaves the field out, or uses a default."""
    profile = (
        "fields:\n  basics.phone: {selector: '.phone'}\n"
        "  basics.label: {selector: '.nope', default: 'Engineer'}\n"
    )
    basics = run(tmp_path, profile).basics
    assert basics.phone is None
    assert basics.label == "Engineer"


def test_fetch_through_local_server(tmp_path: Path, http_root: Path, http_server: str) -> None:
    """The adapter fetches a page over HTTP and resolves relative links against it."""
    shutil.copy(PAGE, http_root / "about.html")
    profile = tmp_path / "p.yaml"
    profile.write_text(
        "fields:\n  basics.url: {selector: '#now a', attr: href, transforms: [absolute_url]}\n",
        encoding="utf-8",
    )
    options = WebOptions(profile=profile, url=f"{http_server}/about.html")
    adapter = WebAdapter()
    resume = adapter.extract(options, AdapterContext(base_dir=tmp_path))
    assert resume.basics.url == f"{http_server}/contact"
    assert adapter.describe_source(options) == f"{http_server}/about.html"


def test_unreachable_and_missing_pages(http_server: str) -> None:
    """AC 4.6 (fetch half): failures name the URL; nothing escapes as a raw exception."""
    with pytest.raises(CvGenError, match=r"HTTP 404"):
        fetch_bytes(f"{http_server}/missing.html")
    # The reserved .invalid domain never resolves, so this fails fast, even offline.
    with pytest.raises(CvGenError, match=r"cannot reach http://cv-gen\.invalid/") as caught:
        fetch_bytes("http://cv-gen.invalid/", timeout=5)
    assert caught.value.hint
    with pytest.raises(CvGenError, match="unsupported URL scheme"):
        fetch_bytes("ftp://example.com/x")


def test_fetch_limits(http_root: Path, http_server: str) -> None:
    """Oversized bodies and plain http under https_only are refused."""
    (http_root / "big.txt").write_bytes(b"x" * 2048)
    with pytest.raises(CvGenError, match="larger than"):
        fetch_bytes(f"{http_server}/big.txt", max_bytes=1024)
    body, _ = fetch_bytes(f"{http_server}/big.txt", https_only=True)  # loopback is allowed
    assert len(body) == 2048
    with pytest.raises(CvGenError, match="plain http"):
        fetch_bytes("http://example.com/x", https_only=True)


def test_fetch_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """A timeout is reported as one, with the limit."""
    import urllib.request

    def slow(*args, **kwargs):
        raise TimeoutError("slow")

    monkeypatch.setattr(urllib.request, "urlopen", slow)
    with pytest.raises(CvGenError, match="timed out after 3s"):
        fetch_bytes("https://example.com/", timeout=3)


def test_helpers() -> None:
    """Loopback detection, decoding fallbacks and reading errors."""
    assert is_loopback("http://localhost:8000/x")
    assert is_loopback("http://[::1]:8000/x")
    assert not is_loopback("http://example.com/")
    assert decode("é".encode(), "no-such-charset") == "é"
    with pytest.raises(CvGenError, match="no such file"):
        read_text(path=Path("missing.html"))
    with pytest.raises(CvGenError, match="no URL or path"):
        read_text()


def test_jsonld_mapping_details() -> None:
    """Person fields map onto basics, including object-valued and single sameAs."""
    basics = person_to_basics(
        {
            "name": "A",
            "image": {"url": "https://example.com/a.png"},
            "address": {"addressCountry": {"name": "PT"}},
            "sameAs": "https://example.org/a",
        }
    )
    assert basics["image"] == "https://example.com/a.png"
    assert basics["location"]["countryCode"] == "PT"
    assert basics["profiles"] == [
        {"network": "example.org", "url": "https://example.org/a", "username": "a"}
    ]
    assert profile_from_url("https://x.com") == {"network": "X", "url": "https://x.com"}


def test_spec_modes(tmp_path: Path) -> None:
    """json, html, attr-list and nested-object specs read what they say."""
    soup = parse_html(
        '<div id="d" class="a b" data-j=\'{"k": [1, 2]}\'><i>x</i> y<br>z</div>'
        '<p class="loc"><span class="c">Porto</span></p>',
        [],
    )
    assert evaluate(FieldSpec(selector="#d", attr="data-j", extract="json"), soup, "f", None) == {
        "k": [1, 2]
    }
    assert evaluate(FieldSpec(selector="#d", attr="class"), soup, "f", None) == "a b"
    assert evaluate(FieldSpec(selector="#d", extract="html"), soup, "f", None).startswith(
        "<i>x</i>"
    )
    assert evaluate(FieldSpec(selector="#d"), soup, "f", None) == "x y z"
    nested = FieldSpec(selector=".loc", fields={"city": FieldSpec(selector=".c")})
    assert evaluate(nested, soup, "f", None) == {"city": "Porto"}
    assert evaluate(FieldSpec(value=None), soup, "f", None) is None
    with pytest.raises(CvGenError, match="not valid JSON"):
        evaluate(FieldSpec(selector="#d", extract="json"), soup, "f", None)
    assert (
        evaluate(FieldSpec(selector="#d", attr="data-none", extract="json"), soup, "f", None)
        is None
    )


def test_spec_validation_and_errors(tmp_path: Path) -> None:
    """Inconsistent specs, bad merges and path clashes are reported."""
    with pytest.raises(ValueError, match="'each' needs 'fields'"):
        FieldSpec(each=".x")
    with pytest.raises(ValueError, match="needs an 'attr'"):
        FieldSpec(extract="attr")
    with pytest.raises(CvGenError, match="needs a mapping"):
        run(tmp_path, "fields:\n  '.': {value: 3}\n")
    record = {"a": 1}
    with pytest.raises(CvGenError, match="already holds a value"):
        set_path(record, "a.b", 2)


def test_profile_loading_errors(tmp_path: Path) -> None:
    """Missing, malformed and invalid profiles are reported against the file."""
    with pytest.raises(CvGenError, match="no such profile"):
        load_profile(tmp_path / "none.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("fields: [\n", encoding="utf-8")
    with pytest.raises(CvGenError, match="not valid YAML"):
        load_profile(bad)
    wrong = tmp_path / "wrong.yaml"
    wrong.write_text("feilds: {}\n", encoding="utf-8")
    with pytest.raises(CvGenError, match="feilds: unknown option"):
        load_profile(wrong)
    many = tmp_path / "many.yaml"
    many.write_text("transforms_module: [a, b]\n", encoding="utf-8")
    assert load_profile(many).transforms_modules == ["a", "b"]


def test_adapter_needs_a_page_and_a_profile(tmp_path: Path) -> None:
    """Without a page, or without a profile, the adapter says what is missing."""
    with pytest.raises(CvGenError, match="needs a page"):
        run(tmp_path, "fields: {}\n", page=None)  # type: ignore[arg-type]
    with pytest.raises(CvGenError, match="needs a profile"):
        WebAdapter().extract(WebOptions(path=PAGE), AdapterContext(base_dir=tmp_path))


def test_default_profile_subclass(tmp_path: Path) -> None:
    """A subclass with a default profile needs no profile option."""

    class Packaged(WebAdapter):
        name = "packaged"
        default_profile = PROFILE

    resume = Packaged().extract(WebOptions(path=PAGE), AdapterContext(base_dir=tmp_path))
    assert resume.basics.headline == "I make slow systems fast."


def test_extracted_data_that_breaks_the_model(tmp_path: Path) -> None:
    """Extracted values the model rejects are reported against the source."""
    profile = (
        "fields:\n  work:\n    each: '.job'\n    fields:\n      startDate: {selector: '.org'}\n"
    )
    with pytest.raises(CvGenError, match=r"(?s)data extracted from .*work\[0\]\.startDate"):
        run(tmp_path, profile)
