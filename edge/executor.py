import os
import time
from pathlib import Path
from urllib.parse import urljoin
from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout
from .redaction import redact


def interpolate(value):
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        name = value[2:-1]
        if name not in os.environ:
            raise RuntimeError(f"Required local variable {name} is not configured")
        return os.environ[name]
    return value


def resolve_locator(page, locator):
    strategy = locator["strategy"]
    exact = locator.get("exact", True)
    if strategy == "role":
        return page.get_by_role(locator["role"], name=locator["name"], exact=exact)
    if strategy == "label":
        return page.get_by_label(locator["value"], exact=exact)
    if strategy == "placeholder":
        return page.get_by_placeholder(locator["value"], exact=exact)
    if strategy == "test_id":
        return page.get_by_test_id(locator["value"])
    if strategy == "css":
        return page.locator(locator["value"])
    raise RuntimeError(f"Unsupported locator strategy: {strategy}")


def collect_interactive_elements(page):
    elements = page.locator("button, a, input, select, textarea, [role], [data-testid]").evaluate_all("""nodes => {
      const visible = n => !!(n.offsetWidth || n.offsetHeight || n.getClientRects().length);
      const role = n => n.getAttribute('role') || ({BUTTON:'button',A:'link',INPUT:'textbox',SELECT:'combobox',TEXTAREA:'textbox'}[n.tagName] || '');
      const name = n => n.getAttribute('aria-label') || n.innerText || n.value || n.getAttribute('placeholder') || '';
      const rows = nodes.filter(visible).slice(0, 100).map(n => ({
        tag:n.tagName.toLowerCase(), role:role(n), name:name(n).trim().slice(0,200),
        label:n.labels && n.labels[0] ? n.labels[0].innerText.trim().slice(0,200) : '',
        placeholder:n.getAttribute('placeholder') || '', test_id:n.getAttribute('data-testid') || '',
        css:n.id ? `#${CSS.escape(n.id)}` : '',
        attributes:{'data-testid':n.getAttribute('data-testid')||'',name:n.getAttribute('name')||'','aria-label':n.getAttribute('aria-label')||''},
        context:(n.parentElement?.innerText || '').trim().slice(0,300)
      }));
      return rows.map((row, _, all) => ({...row, unique:all.filter(other => other.role===row.role && other.name===row.name).length===1}));
    }""")
    return redact(elements)


def _postcondition(page, postcondition):
    if not postcondition:
        return
    if "url_contains" in postcondition and postcondition["url_contains"] not in page.url:
        raise AssertionError(f"postcondition expected URL containing {postcondition['url_contains']}")
    if "text_visible" in postcondition:
        page.get_by_text(postcondition["text_visible"], exact=False).wait_for(state="visible", timeout=10000)


def execute_step(page, step, base_url):
    action = step["action"]
    timeout = step.get("timeout_ms", 10000)
    if action == "navigate":
        page.goto(urljoin(base_url, interpolate(step["url"])), wait_until="domcontentloaded", timeout=timeout)
    elif action == "assert_url":
        if interpolate(step["value"]) not in page.url:
            raise AssertionError(f"expected URL containing {step['value']}")
    else:
        locator = resolve_locator(page, step["locator"])
        if action == "click": locator.click(timeout=timeout)
        elif action == "fill": locator.fill(interpolate(step["value"]), timeout=timeout)
        elif action == "select": locator.select_option(interpolate(step["value"]), timeout=timeout)
        elif action == "assert_text":
            if interpolate(step["value"]) not in locator.inner_text(timeout=timeout): raise AssertionError(f"expected text {step['value']}")
        elif action == "wait_for": locator.wait_for(state="visible", timeout=timeout)
        else: raise RuntimeError(f"Unsupported action: {action}")
    _postcondition(page, step.get("postcondition"))


def failure_code(exc):
    text = str(exc).lower()
    if isinstance(exc, PlaywrightTimeout): return "locator_timeout"
    if "strict mode violation" in text: return "ambiguous_locator"
    if "net::" in text or "connection" in text: return "network_error"
    if isinstance(exc, AssertionError): return "postcondition_failed"
    return "execution_error"


def execute_workflow(browser, job, artifact_dir):
    run_id, spec = job["run_id"], job["spec"]
    # Local desktop runs hit Odoo via localhost; Dockerized workers resolve the service
    # via the compose network name. Prefer localhost for the default host-based demo flow.
    base_url = os.getenv("ODOO_BASE_URL", "http://localhost:8069")
    context = browser.new_context()
    page = context.new_page()
    artifact_path = Path(artifact_dir) / str(run_id)
    artifact_path.mkdir(parents=True, exist_ok=True)
    trace_path = artifact_path / "trace.zip"
    context.tracing.start(screenshots=True, snapshots=True, sources=False)
    steps = []
    console_errors = []
    page.on("console", lambda message: console_errors.append(message.text[:500]) if message.type == "error" else None)
    try:
        for step in spec["steps"]:
            started = time.monotonic()
            try:
                execute_step(page, step, base_url)
                steps.append({"step_id": step["id"], "status": "passed", "duration_ms": int((time.monotonic()-started)*1000), "detail": {"url": page.url}})
            except (PlaywrightError, AssertionError, RuntimeError) as exc:
                steps.append({"step_id": step["id"], "status": "failed", "duration_ms": int((time.monotonic()-started)*1000), "detail": {"url": page.url}})
                screenshot_path = artifact_path / "failure.png"
                try:
                    page.screenshot(path=str(screenshot_path), full_page=True)
                except Exception:
                    screenshot_path = artifact_path / "failure.png"
                return {
                    "status": "failed", "steps": redact(steps),
                    "failure": {"step_id": step["id"], "code": failure_code(exc), "message": str(exc)[:4000], "evidence": {"url": page.url, "console_errors": console_errors[-10:], "local_screenshot": str(screenshot_path) if screenshot_path.exists() else ""}},
                    "interactive_elements": collect_interactive_elements(page),
                }
        return {"status": "passed", "steps": redact(steps)}
    finally:
        context.tracing.stop(path=str(trace_path))
        context.close()

