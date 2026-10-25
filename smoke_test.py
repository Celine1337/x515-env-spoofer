import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\Spoofer")
import chess_env_spoofer as m
from playwright.sync_api import sync_playwright

fp = m.new_fingerprint("test-profile")
print("fingerprint generated:", fp["profile"], "| canvas seed:", fp["seeds"]["canvas"])

script = m.stealth_script(fp)
assert '"hardware"' in script, "stealth CFG injection failed"

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(viewport={"width": 1920, "height": 1040})
    ctx.add_init_script(script)
    page = ctx.new_page()
    page.goto("about:blank")
    checks = page.evaluate("""() => {
        const c = document.createElement('canvas'); c.width=300; c.height=150;
        const x = c.getContext('2d'); x.fillStyle = '#3a7'; x.fillRect(0,0,300,150);
        x.font = '16px Arial'; x.textBaseline = 'alphabetic';
        x.fillText('chess::fingerprint::2025', 10, 40);
        const h1 = c.toDataURL();
        const wg = document.createElement('canvas');
        const g = wg.getContext('webgl');
        return {
            webdriver: String(navigator.webdriver),
            hardwareConcurrency: navigator.hardwareConcurrency,
            deviceMemory: navigator.deviceMemory,
            platform: navigator.platform,
            pluginsLen: navigator.plugins.length,
            plugin0: navigator.plugins[0] ? navigator.plugins[0].name : null,
            languages: navigator.languages.join(','),
            ua: /Headless/.test(navigator.userAgent) ? 'LEAK-HEADLESS' : 'CLEAN-UA',
            hasChromeObj: typeof window.chrome === 'object' && !!window.chrome.runtime,
            webglVendor: g.getParameter(0x9245),
            webglRenderer: g.getParameter(0x9246),
            canvasHash: h1.slice(-28),
        };
    }""")
    checks["canvasDeterministic"] = page.evaluate(
        """() => {
            const c = document.createElement('canvas'); c.width=300; c.height=150;
            const x = c.getContext('2d'); x.fillStyle = '#3a7'; x.fillRect(0,0,300,150);
            x.font = '16px Arial'; x.textBaseline = 'alphabetic';
            x.fillText('chess::fingerprint::2025', 10, 40);
            return c.toDataURL().slice(-28) === %s;
        }""" % ('"' + checks["canvasHash"] + '"')
    )
    for k, v in checks.items():
        print("  %-20s : %s" % (k, v))
    ctx.close()
    browser.close()

ok_names = (
    checks["webdriver"] == "false"
    and checks["hardwareConcurrency"] == 4
    and checks["deviceMemory"] == 8
    and checks["pluginsLen"] >= 5
    and checks["languages"] == "en-US,en"
    and checks["ua"] == "CLEAN-UA"
    and checks["hasChromeObj"] is True
    and checks["webglVendor"] == "Intel Inc."
    and checks["webglRenderer"] != ""
    and checks["canvasDeterministic"] is True
)
print("SMOKE-TEST:", "PASS" if ok_names else "FAIL")
