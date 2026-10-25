#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Environment fingerprint suite (ASUS X515EA profile), Playwright isolation + runtime JS patching."""

import os
import sys
import json
import time
import shutil
import random
import subprocess
import urllib.request
from pathlib import Path


def _boot_console():
    if sys.platform != "win32" or sys.stdout is not None:
        return
    import ctypes
    k32 = ctypes.windll.kernel32
    if not k32.AttachConsole(-1):
        k32.AllocConsole()
    import msvcrt

    def grab(h, mode):
        h = k32.GetStdHandle(h)
        if not h or h == -1:
            return None
        fd = msvcrt.open_osfhandle(h, 0)
        if fd < 0:
            return None
        return os.fdopen(fd, mode, buffering=1, encoding="utf-8", errors="replace")

    out, err, inp = grab(-11, "w"), grab(-12, "w"), grab(-10, "r")
    sys.stdout = sys.stdout or out
    sys.stderr = sys.stderr or err
    sys.stdin = sys.stdin or inp


_boot_console()

from colorama import init as colorama_init, Fore, Style
colorama_init(autoreset=True)

APP_NAME = "X515 Env Spoofer"
APP_VER = "1.0.0"


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT = app_root()
PROFILE_DIR = ROOT / "profiles"
STATE_FILE = ROOT / "state.json"
LOG_FILE = ROOT / "spoofer.log"

HARDWARE = {
    "hardwareConcurrency": 4,  # Core i3-1115G4
    "deviceMemory": 8,  # 12 GB, browser API tops out at 8
    "platform": "Win32",
    "vendor": "Google Inc.",
}

WEBGL = {
    "vendor": "Intel Inc.",
    "renderer": "ANGLE (Intel, Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0)",
}

SCREEN = {
    "width": 1920,
    "height": 1080,
    "availWidth": 1920,
    "availHeight": 1040,
    "colorDepth": 24,
    "pixelDepth": 24,
    "devicePixelRatio": 1.0,
    "outerWidth": 1920,
    "outerHeight": 1040,
}

IDENTITY = {
    "lang": "en-US",
    "languages": ["en-US", "en"],
    "timezone": "America/New_York",
}

PURGE_TARGETS = ("chrome", "edge", "firefox", "temp", "dns")


def hr():
    print(Fore.CYAN + "-" * 72)


def dbl():
    print(Fore.CYAN + "=" * 72)


def ok(m):
    print(Fore.GREEN + "[ OK ] " + m)


def warn(m):
    print(Fore.YELLOW + "[ !! ] " + m)


def err(m):
    print(Fore.RED + "[ERR ] " + m)


def info(m):
    print(Fore.CYAN + "[ -> ] " + m)


def ask(m):
    return input(Fore.LIGHTCYAN_EX + m).strip()


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    dbl()
    print(Fore.LIGHTMAGENTA_EX + "  " + APP_NAME.upper() + Fore.WHITE + "  -  deep environment spoofer  v" + APP_VER)
    dbl()
    print(Fore.WHITE + "   hardware : " + Fore.LIGHTGREEN_EX + "ASUS X515EA-BQ950 / i3-1115G4 / 12GB / Intel UHD / 1080p")
    print(Fore.WHITE + "   root     : " + str(ROOT))
    dbl()


def logline(s: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("%s | %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), s))
    except Exception:
        pass


def mulberry32(seed_int):
    st = [seed_int & 0xFFFFFFFF]

    def rnd():
        st[0] = (st[0] + 0x6D2B79F5) & 0xFFFFFFFF
        t = st[0]
        t = (t ^ (t >> 15)) * (t | 1) & 0xFFFFFFFF
        t = (t ^ (t + ((t ^ (t >> 7)) * (t | 61) & 0xFFFFFFFF))) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 0x100000000

    return rnd


def new_seed():
    return random.randrange(0, 2 ** 31 - 1)


def new_fingerprint(profile_name: str) -> dict:
    fp = {
        "profile": profile_name,
        "hardware": dict(HARDWARE),
        "webgl": dict(WEBGL),
        "screen": dict(SCREEN),
        "identity": json.loads(json.dumps(IDENTITY)),
        "noise": {
            "canvasDensity": random.choice([37, 53, 61, 73]),
            "canvasAmp": 1,
            "audioStride": random.choice([7499, 9277, 10091]),
            "audioAmp": 1e-7,
            "jsStride": random.choice([97, 113, 131]),
        },
        "seeds": {
            "canvas": new_seed(),
            "webgl": new_seed(),
            "audio": new_seed(),
            "misc": new_seed(),
        },
    }
    fp["noise"]["canvasBias"] = round(0.55 + mulberry32(fp["seeds"]["canvas"])() * 0.35, 4)
    return fp


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(st: dict):
    STATE_FILE.write_text(json.dumps(st, indent=2), encoding="utf-8")


def list_profiles() -> list:
    if not PROFILE_DIR.exists():
        return []
    return sorted([p.name for p in PROFILE_DIR.iterdir() if p.is_dir()])


class Profile:
    def __init__(self, name: str):
        self.name = name
        self.dir = PROFILE_DIR / name
        self.fp_path = self.dir / "fingerprint.json"
        self.cfg_path = self.dir / "config.json"
        self.data_dir = self.dir / "chrome-data"

    def ensure(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        if not self.fp_path.exists():
            self.fp_path.write_text(json.dumps(new_fingerprint(self.name), indent=2), encoding="utf-8")
        if not self.cfg_path.exists():
            self.cfg_path.write_text(
                json.dumps({"proxy": {"enabled": False, "host": "", "port": "", "user": "", "pass": ""}}, indent=2),
                encoding="utf-8",
            )

    def fingerprint(self) -> dict:
        self.ensure()
        return json.loads(self.fp_path.read_text(encoding="utf-8"))

    def save_fp(self, fp: dict):
        self.ensure()
        self.fp_path.write_text(json.dumps(fp, indent=2), encoding="utf-8")

    def config(self) -> dict:
        self.ensure()
        return json.loads(self.cfg_path.read_text(encoding="utf-8"))

    def save_cfg(self, cfg: dict):
        self.ensure()
        self.cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def current_profile() -> Profile:
    st = load_state()
    name = st.get("last_profile") or "asus-x515ea"
    p = Profile(name)
    p.ensure()
    st["last_profile"] = name
    save_state(st)
    return p


def pick_profile() -> Profile:
    names = list_profiles()
    info("available profiles: " + (", ".join(names) if names else "(none yet)"))
    new = ask("profile name ? [enter = current / type = add-switch] : ")
    if new:
        p = Profile(new)
        p.ensure()
        st = load_state()
        st["last_profile"] = new
        save_state(st)
        ok("profile -> " + new)
        return p
    return current_profile()


STEALTH_JS = r"""(() => {
'use strict';
const CFG = /*__CFG__*/{};
if (!CFG || !CFG.hardware) return;

const def = (o,k,get) => { try { Object.defineProperty(o,k,{get,configurable:true}); } catch(e){} };
const hash32 = (str,seed) => { let h=(seed>>>0); for(let i=0;i<str.length;i++){ h=Math.imul(h^str.charCodeAt(i),0x01000193)>>>0; } return h>>>0; };
const mb32 = (a) => { a=a>>>0; return () => { a=(a+0x6D2B79F5)|0; let t=Math.imul(a^(a>>>15),1|a); t=(t+Math.imul(t^(t>>>7),61|t))^t; return ((t^(t>>>14))>>>0)/4294967296; }; };
const nat = (fn,name) => { try { Object.defineProperty(fn,'toString',{value:()=>'function '+(name||fn.name||'')+'() { [native code] }'}); } catch(e){} return fn; };
const clamp = (v) => (v<0?0:(v>255?255:v));

// navigator surface
try { def(Object.getPrototypeOf(navigator),'webdriver',()=>false); } catch(e){}
try { def(navigator,'webdriver',()=>false); } catch(e){}
try {
  if (/HeadlessChrome/.test(navigator.userAgent)) {
    const fixed = navigator.userAgent.replace(/HeadlessChrome/g,'Chrome');
    def(navigator,'userAgent',()=>fixed);
  }
  if (/HeadlessChrome/.test(String(navigator.appVersion||''))) {
    def(navigator,'appVersion',()=>String(navigator.appVersion||'').replace(/HeadlessChrome/g,'Chrome'));
  }
} catch(e){}
def(navigator,'platform',()=>CFG.hardware.platform);
def(navigator,'vendor',()=>CFG.hardware.vendor);
def(navigator,'language',()=>CFG.identity.lang);
const langs = CFG.identity.languages.slice(0);
def(navigator,'languages',()=>langs);
def(navigator,'hardwareConcurrency',()=>CFG.hardware.hardwareConcurrency);
def(navigator,'deviceMemory',()=>CFG.hardware.deviceMemory);
def(navigator,'maxTouchPoints',()=>0);

// user agent data / client hints
(() => {
  try {
    const real = navigator.userAgentData;
    if (!real) return;
    const ua = navigator.userAgent || '';
    const m = ua.match(/Chrome\/(\d+)\.(\d+)\.(\d+)\.(\d+)/);
    const maj = m ? m[1] : '100';
    const full = m ? m[0].split('/')[1] : maj + '.0.0.0';
    const src = (real.brands && real.brands.length) ? real.brands : [{brand:'Chromium',version:maj},{brand:'Not-A.Brand',version:'99'},{brand:'Google Chrome',version:maj}];
    const gl = src.find(b=>/Google Chrome/i.test(b.brand));
    const cr = src.find(b=>/^Chromium$/i.test(b.brand));
    const nb = src.find(b=>/Not[_-]/i.test(b.brand));
    const brands = [ {brand:(cr&&cr.brand)||'Chromium',version:(cr&&cr.version)||maj},
                     {brand:(gl&&gl.brand)||'Google Chrome',version:(gl&&gl.version)||maj},
                     {brand:(nb&&nb.brand)||'Not-A.Brand',version:(nb&&nb.version)||'99'} ];
    const data = { brands: brands, mobile:false, platform:'Windows',
                   brandVersion:maj, fullVersion: full, platformVersion:'15.0.0',
                   architecture:'x86', bitness:'64', wow64:false, model:'' };
    def(navigator,'userAgentData',()=>({
      brands:brands.slice(), mobile:false, platform:'Windows',
      toJSON(){ return {brands:brands.slice(), mobile:false, platform:'Windows'}; },
      getHighEntropyValues(h){ return new Promise((res)=>{ const out={}; (h||[]).forEach(k=>{ if(k in data) out[k]=data[k]; }); res(out); }); }
    }));
  } catch(e){}
})();

// screen / window geometry
(() => {
  try {
    const S = CFG.screen, sc = window.screen;
    if (sc) {
      [['width',S.width],['height',S.height],['availWidth',S.availWidth],['availHeight',S.availHeight],
       ['colorDepth',S.colorDepth],['pixelDepth',S.pixelDepth],['availLeft',0],['availTop',0]]
       .forEach(kv => def(sc, kv[0], ()=>S[kv[0]] !== undefined ? S[kv[0]] : 0));
    }
    def(window,'devicePixelRatio',()=>S.devicePixelRatio);
    def(window,'outerWidth',()=>S.outerWidth);
    def(window,'outerHeight',()=>S.outerHeight);
    def(window,'screenX',()=>0); def(window,'screenY',()=>0);
    def(window,'screenLeft',()=>0); def(window,'screenTop',()=>0);
  } catch(e){}
})();

// plugins / mimeTypes
(() => {
  try {
    if (!window.Plugin || !window.PluginArray || !window.MimeType || !window.MimeTypeArray) return;
    const pdf = Object.create(window.MimeType.prototype);
    def(pdf,'type',()=>'application/pdf');
    def(pdf,'suffixes',()=>'pdf');
    def(pdf,'description',()=>'Portable Document Format');
    const names = ['PDF Viewer','Chrome PDF Viewer','Chromium PDF Viewer','Microsoft Edge PDF Viewer','WebKit built-in PDF'];
    const plugins = names.map(function(nm){
      const p = Object.create(window.Plugin.prototype);
      def(p,'name',()=>nm);
      def(p,'description',()=>'Portable Document Format');
      def(p,'filename',()=>'internal-pdf-viewer');
      def(p,'length',()=>1);
      def(p,0,()=>pdf);
      p.item = nat(function(i){ return i===0 ? pdf : null; },'item');
      p.namedItem = nat(function(t){ return t==='application/pdf' ? pdf : null; },'namedItem');
      return p;
    });
    def(pdf,'enabledPlugin',()=>plugins[0]);
    const pluginArr = Object.create(window.PluginArray.prototype);
    plugins.forEach((p,i)=>def(pluginArr,i,()=>p));
    def(pluginArr,'length',()=>plugins.length);
    pluginArr.item = nat(function(i){ return typeof i==='number' ? (plugins[i]||null) : null; },'item');
    pluginArr.namedItem = nat(function(n){ return plugins.find(p=>p.name===n)||null; },'namedItem');
    pluginArr.refresh = nat(function(){},'refresh');
    def(navigator,'plugins',()=>pluginArr);
    const mimeArr = Object.create(window.MimeTypeArray.prototype);
    def(mimeArr,0,()=>pdf);
    def(mimeArr,'length',()=>1);
    mimeArr.item = nat(function(i){ return i===0 ? pdf : null; },'item');
    mimeArr.namedItem = nat(function(t){ return t==='application/pdf' ? pdf : null; },'namedItem');
    def(navigator,'mimeTypes',()=>mimeArr);
  } catch(e){}
})();

// permissions / Notification
(() => {
  try {
    if (window.Notification) def(Notification,'permission',()=>'default');
    if (navigator.permissions && navigator.permissions.query) {
      const orig = navigator.permissions.query.bind(navigator.permissions);
      navigator.permissions.query = nat(function(d){
        if (d && d.name === 'notifications') {
          return Promise.resolve({state:'prompt', onchange:null,
            addEventListener(){}, removeEventListener(){}, dispatchEvent(){return false;}});
        }
        return orig(d);
      },'query');
    }
  } catch(e){}
})();

// window.chrome
(() => {
  try {
    if (!window.chrome) Object.defineProperty(window,'chrome',{value:{},configurable:true});
    const c = window.chrome;
    if (!c.app) c.app = { isInstalled:false,
      InstallState:{DISABLED:'disabled',INSTALLED:'installed',NOT_INSTALLED:'not_installed'},
      RunningState:{CANNOT_RUN:'cannot_run',READY_TO_RUN:'ready_to_run',RUNNING:'running'} };
    if (!c.csi) c.csi = nat(function(){ return {startE:Date.now()-1000,onloadT:Date.now()-500,pageT:1000,tran:15}; },'csi');
    if (!c.loadTimes) c.loadTimes = nat(function(){ const t0=performance.timeOrigin/1000;
      return {requestTime:t0,startLoadTime:t0,commitLoadTime:t0+0.05,finishDocumentLoadTime:t0+0.2,finishLoadTime:t0+0.3,firstPaintTime:t0+0.25,firstPaintAfterLoadTime:0,navigationType:'Other',wasFetchedViaSpdy:true,wasNpnNegotiated:true,npnNegotiatedProtocol:'h2',wasAlternateProtocolAvailable:false}; },'loadTimes');
    if (!c.runtime) c.runtime = {};
    const r = c.runtime;
    if (!r.PlatformOs) r.PlatformOs = {MAC:'mac',WIN:'win',ANDROID:'android',CROS:'cros',LINUX:'linux',OPENBSD:'openbsd'};
    if (!r.PlatformArch) r.PlatformArch = {ARM:'arm',X86_32:'x86-32',X86_64:'x86-64',MIPS:'mips',MIPS64:'mips64'};
    if (!r.PlatformNaclArch) r.PlatformNaclArch = {ARM:'arm',X86_32:'x86-32',X86_64:'x86-64'};
    if (!r.RequestUpdateCheckStatus) r.RequestUpdateCheckStatus = {NO_UPDATE:'no_update',THROTTLED:'throttled',UPDATE_AVAILABLE:'update_available'};
    if (!r.OnInstalledReason) r.OnInstalledReason = {CHROME_UPDATE:'chrome_update',INSTALL:'install',MODULE_UPDATE:'module_update',SHARED_MODULE_UPDATE:'shared_module_update',UPDATE:'update'};
    if (!r.OnRestartRequiredReason) r.OnRestartRequiredReason = {APP_UPDATE:'app_update',OS_UPDATE:'os_update',PERIODIC:'periodic'};
    if (typeof r.sendMessage !== 'function') r.sendMessage = nat(function(){},'sendMessage');
    if (typeof r.connect !== 'function') r.connect = nat(function(){
      return { disconnect(){}, postMessage(){}, name:'',
        onMessage:{addListener(){},removeListener(){},hasListener(){return false;}},
        onDisconnect:{addListener(){},removeListener(){},hasListener(){return false;}} };
    },'connect');
  } catch(e){}
})();

// canvas / WebGL noise
(() => {
  try {
    const N = CFG.noise, SC = CFG.seeds.canvas;
    const rotBuf = (data, salt) => {
      const prng = mb32(hash32(salt, SC));
      const stride = N.canvasDensity | 0;
      for (let i = 0; i < data.length; i += stride) {
        if (prng() < N.canvasBias) {
          data[i] = clamp(data[i] + (prng() < 0.5 ? -1 : 1));
        }
      }
    };
    const origGet = (CanvasRenderingContext2D) ? CanvasRenderingContext2D.prototype.getImageData : null;
    if (origGet) {
      CanvasRenderingContext2D.prototype.getImageData = nat(function(x,y,w,h){
        const img = origGet.call(this, x, y, w, h);
        try { rotBuf(img.data, 'get:'+ (this.canvas && this.canvas.width|0) +'x'+ (this.canvas && this.canvas.height|0) +':'+(x|0)+','+(y|0)+':'+(w|0)+'x'+(h|0)); } catch(e){}
        return img;
      },'getImageData');
    }
    const oData = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = nat(function(){
      try {
        if (this.width && this.height) {
          const sh = document.createElement('canvas');
          sh.width = this.width; sh.height = this.height;
          const sx = sh.getContext('2d');
          if (sx) {
            sx.drawImage(this, 0, 0);
            const img = sx.getImageData(0, 0, sh.width, sh.height);
            sx.putImageData(img, 0, 0);
            return oData.apply(sh, arguments);
          }
        }
      } catch(e){}
      return oData.apply(this, arguments);
    },'toDataURL');
    if (HTMLCanvasElement.prototype.toBlob) {
      const oBlob = HTMLCanvasElement.prototype.toBlob;
      HTMLCanvasElement.prototype.toBlob = nat(function(cb){
        try {
          if (this.width && this.height) {
            const sh = document.createElement('canvas');
            sh.width = this.width; sh.height = this.height;
            const sx = sh.getContext('2d');
            if (sx) {
              sx.drawImage(this, 0, 0);
              const img = sx.getImageData(0, 0, sh.width, sh.height);
              sx.putImageData(img, 0, 0);
              return oBlob.call(sh, cb, arguments[1], arguments[2]);
            }
          }
        } catch(e){}
        return oBlob.apply(this, arguments);
      },'toBlob');
    }
  } catch(e){}
})();

// WebGL parameters
(() => {
  try {
    const UNMASKED_VENDOR_WEBGL = 0x9245;
    const UNMASKED_RENDERER_WEBGL = 0x9246;
    const MAX_TEXTURE_SIZE = 0x0D33;
    const MAX_RENDERBUFFER_SIZE = 0x84E8;
    const MAX_CUBE_MAP_TEXTURE_SIZE = 0x851C;
    const map = {};
    map[UNMASKED_VENDOR_WEBGL] = CFG.webgl.vendor;
    map[UNMASKED_RENDERER_WEBGL] = CFG.webgl.renderer;
    map[MAX_TEXTURE_SIZE] = 16384;
    map[MAX_RENDERBUFFER_SIZE] = 16384;
    map[MAX_CUBE_MAP_TEXTURE_SIZE] = 16384;
    const patch = (proto) => {
      if (!proto || !proto.getParameter) return;
      const orig = proto.getParameter;
      proto.getParameter = nat(function(p){
        try { if (map[p] !== undefined) return map[p]; } catch(e){}
        return orig.call(this, p);
      },'getParameter');
    };
    if (window.WebGLRenderingContext) patch(window.WebGLRenderingContext.prototype);
    if (window.WebGL2RenderingContext) patch(window.WebGL2RenderingContext.prototype);
  } catch(e){}
})();

// audio
(() => {
  try {
    if (window.AudioBuffer && AudioBuffer.prototype.getChannelData) {
      const orig = AudioBuffer.prototype.getChannelData;
      AudioBuffer.prototype.getChannelData = nat(function(ch){
        const data = orig.call(this, ch);
        try {
          if (data && data.length && !this.__spoofed) {
            Object.defineProperty(this, '__spoofed', {enumerable:false, value:true});
            const prng = mb32(hash32('audio:'+data.length, CFG.seeds.audio));
            const s = CFG.noise.audioStride|0, amp = +CFG.noise.audioAmp;
            for (let i=0;i<data.length;i+=s) data[i] = data[i] + (prng()<0.5?-amp:amp);
          }
        } catch(e){}
        return data;
      },'getChannelData');
    }
    if (window.AnalyserNode && AnalyserNode.prototype.getFloatFrequencyData) {
      const orig = AnalyserNode.prototype.getFloatFrequencyData;
      AnalyserNode.prototype.getFloatFrequencyData = nat(function(arr){
        orig.call(this, arr);
        try {
          if (arr && arr.length) {
            const prng = mb32(hash32('analyser:'+arr.length, CFG.seeds.audio));
            const s = CFG.noise.audioStride|0, amp = +CFG.noise.audioAmp;
            for (let i=0;i<arr.length;i+=s) arr[i] = arr[i] + (prng()<0.5?-amp:amp);
          }
        } catch(e){}
      },'getFloatFrequencyData');
    }
  } catch(e){}
})();

// automation artifacts
(() => {
  try {
    const rx = /^\$cdc_|^\$chrome_asyncScriptInfo|__driver|__webdriver|__selenium|__fxdriver|__nightmare|_phantom|callPhantom|domAutomation/;
    Object.keys(window).forEach(k => { try { if (rx.test(k)) delete window[k]; } catch(e){} });
    Object.keys(document).forEach(k => { try { if (rx.test(k)) delete document[k]; } catch(e){} });
  } catch(e){}
})();
})();
"""


def stealth_script(fp: dict) -> str:
    return STEALTH_JS.replace("/*__CFG__*/{}", json.dumps(fp, ensure_ascii=True))


def _ms_browsers_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ms-playwright"


def _ensure_browsers():
    if not getattr(sys, "frozen", False):
        return
    if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_ms_browsers_dir())
    bdir = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
    if bdir.exists() and any(bdir.glob("chromium-*")):
        return
    import playwright
    driver_dir = Path(playwright.__file__).resolve().parent / "driver"
    node, cli = driver_dir / "node.exe", driver_dir / "package" / "cli.js"
    if not (node.exists() and cli.exists()):
        err("chromium not found and bundled installer unavailable")
        err("run once: pip install playwright && python -m playwright install chromium")
        return
    ok("chromium missing -> downloading (~200 MB, one time)")
    try:
        subprocess.run([str(node), str(cli), "install", "chromium"], check=True)
        ok("chromium installed")
    except Exception as e:
        err("chromium download failed: " + str(e))


def launch_browser(fp: dict, cfg: dict, fresh=False):
    engine = "playwright"
    try:
        from patchright.sync_api import sync_playwright
        engine = "patchright"
    except ImportError:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            err("neither patchright nor playwright is installed")
            err("-> pip install patchright && python -m patchright install chromium")
            return None
        warn("engine: playwright (google sign-in will block) -> pip install patchright")

    info("engine: " + engine)
    _ensure_browsers()

    temp_holder = {}
    if fresh:
        import tempfile
        temp_holder["dir"] = Path(tempfile.mkdtemp(prefix="x515_"))

    user_data_dir = str(temp_holder["dir"]) if fresh else str(PROFILE_DIR / fp["profile"] / "chrome-data")

    try:
        ps = ("Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
              "Where-Object { $_.CommandLine -match 'ms-playwright' } | "
              "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=30)
    except Exception:
        pass

    launch_kw = dict(
        headless=False,
        viewport=None,
        screen={"width": SCREEN["width"], "height": SCREEN["height"]},
        locale=IDENTITY["lang"],
        timezone_id=IDENTITY["timezone"],
        args=[
            "--disable-blink-features=AutomationControlled",
            "--window-size=1920,1040",
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            "--lang=en-US",
        ],
        ignore_default_args=["--enable-automation"],
    )
    if cfg.get("proxy", {}).get("enabled"):
        pr = cfg["proxy"]
        launch_kw["proxy"] = {"server": "http://%s:%s" % (pr["host"], pr["port"]),
                              "username": pr.get("user") or "", "password": pr.get("pass") or ""}

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(user_data_dir, **launch_kw)
        ctx.add_init_script(stealth_script(fp))
        page = ctx.new_page()
        try:
            page.goto("https://www.chess.com/", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            warn("goto chess.com failed: " + str(e))
            warn("check proxy / connection; browser still open for manual nav.")
        ok("browser live - fingerprint active")
        info("user data dir " + str(temp_holder["dir"] if fresh else Path(user_data_dir)))
        try:
            while ctx.pages:
                time.sleep(1.0)
        except KeyboardInterrupt:
            warn("user break - closing context")
        try:
            ctx.close()
        except Exception:
            pass
        if fresh:
            shutil.rmtree(temp_holder["dir"], ignore_errors=True)
            ok("temp user data dir wiped")
    return True


def _rm_tree(p: Path, removed: list):
    try:
        if p.is_dir():
            shutil.rmtree(str(p))
            removed.append(str(p))
    except Exception:
        pass


def _rm_file(p: Path, removed: list):
    try:
        if p.is_file():
            p.unlink()
            removed.append(str(p))
    except Exception:
        pass


def purge_chromium_like(kind: str) -> list:
    base = Path(os.environ.get("LOCALAPPDATA", ""))
    if kind == "chrome":
        root = base / "Google" / "Chrome" / "User Data"
    else:
        root = base / "Microsoft" / "Edge" / "User Data"
    removed = []
    if not root.exists():
        return removed
    for prof in [d for d in root.iterdir() if d.is_dir()]:
        if prof.name != "Default" and not prof.name.startswith("Profile"):
            continue
        for c in (prof / "Network" / "Cookies", prof / "Cookies"):
            _rm_file(c, removed)
            _rm_file(Path(str(c) + "-journal"), removed)
            _rm_file(Path(str(c) + "-shm"), removed)
            _rm_file(Path(str(c) + "-wal"), removed)
        _rm_tree(prof / "Local Storage" / "leveldb", removed)
        _rm_tree(prof / "Session Storage", removed)
        _rm_tree(prof / "IndexedDB", removed)
        _rm_tree(prof / "Cache", removed)
        _rm_tree(prof / "Code Cache", removed)
        _rm_tree(prof / "GPUCache", removed)
        _rm_tree(prof / "Service Worker" / "CacheStorage", removed)
        _rm_tree(prof / "Service Worker" / "ScriptCache", removed)
    return removed


def purge_firefox() -> list:
    prof_root = Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox" / "Profiles"
    removed = []
    if not prof_root.exists():
        return removed
    for prof in [d for d in prof_root.iterdir() if d.is_dir()]:
        for fname in ("cookies.sqlite", "cookies.sqlite-wal", "cookies.sqlite-shm",
                      "places.sqlite", "places.sqlite-wal", "places.sqlite-shm",
                      "formhistory.sqlite", "webappsstore.sqlite", "sessionstore.jsonlz4"):
            _rm_file(prof / fname, removed)
        _rm_tree(prof / "storage" / "default", removed)
        _rm_tree(prof / "cache2", removed)
        _rm_tree(prof / "startupCache", removed)
    return removed


def kill_browser_procs():
    for exe in ("chrome.exe", "msedge.exe", "firefox.exe"):
        try:
            os.system('taskkill /IM %s /F /T >nul 2>&1' % exe)
        except Exception:
            pass


def dns_flush():
    if os.name != "nt":
        return False
    return os.system("ipconfig /flushdns >nul 2>&1") == 0


def windows_temp_purge(removed: list):
    tmp = os.environ.get("TEMP", "")
    if not tmp or not os.path.isdir(tmp):
        return
    now = time.time()
    for entry in Path(tmp).iterdir():
        try:
            if now - entry.stat().st_mtime > 86400:
                if entry.is_file():
                    entry.unlink()
                elif entry.is_dir():
                    shutil.rmtree(str(entry), ignore_errors=True)
                removed.append(str(entry))
        except Exception:
            continue


def deep_purge(quiet=False):
    pick_profile()
    targets = [t for t in (load_state().get("purge_targets") or PURGE_TARGETS) if t in PURGE_TARGETS]
    removed = []
    for t in targets:
        if t == "chrome":
            removed.extend(purge_chromium_like("chrome"))
        elif t == "edge":
            removed.extend(purge_chromium_like("edge"))
        elif t == "firefox":
            removed.extend(purge_firefox())
        elif t == "temp":
            windows_temp_purge(removed)
        elif t == "dns":
            if dns_flush():
                if not quiet:
                    ok("dns cache flushed")
            elif not quiet:
                warn("dns flush skipped (needs admin?)")
    if not quiet:
        dbl()
        info("purge results")
        for r in removed[:60]:
            print("   - " + r)
        if len(removed) > 60:
            print("   ... +%d more" % (len(removed) - 60))
        ok("%d storage / cache items removed" % len(removed))
    save_state({"purge_targets": targets, "last_profile": load_state().get("last_profile")})
    return removed


def proxy_url(cfg: dict) -> str:
    pr = cfg.get("proxy", {})
    if not pr.get("enabled") or not pr.get("host"):
        return ""
    auth = "%s:%s@" % (pr["user"], pr.get("pass", "")) if pr.get("user") else ""
    return "http://%s%s:%s" % (auth, pr["host"], pr["port"])


def fetch(url, proxy=None, timeout=15):
    ph = urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})
    h = urllib.request.build_opener(ph)
    h.addheaders = [("User-Agent", "Mozilla/5.0")]
    return h.open(url, timeout=timeout).read()


def test_network():
    prx = proxy_url(current_profile().config()) or None
    info("probe via %s" % (prx if prx else "direct (no proxy)"))
    try:
        ip = fetch("https://api.ipify.org/", prx).decode("utf-8")
        ok("external IP        : " + ip)
    except Exception as e:
        err("external IP probe failed: " + str(e))
        return
    try:
        data = fetch("https://www.chess.com/", prx, timeout=20)
        ok("chess.com reachable (%d bytes)" % len(data))
    except Exception as e:
        err("chess.com probe failed: " + str(e))


def configure_proxy():
    p = current_profile()
    cfg = p.config()
    while True:
        clear()
        banner()
        pr = cfg.get("proxy", {})
        info("current proxy:")
        print("   enabled : " + str(pr.get("enabled")))
        print("   server  : " + (pr.get("host") or "(none)") + ":" + (pr.get("port") or "(port)"))
        print("   user    : " + (pr.get("user") or "(none)"))
        hr()
        print(Fore.WHITE + "  [1] set proxy     [2] toggle on/off     [3] clear     [0] back")
        c = ask("> ")
        if c == "1":
            cfg["proxy"]["host"] = ask("host or ip    : ")
            cfg["proxy"]["port"] = ask("port          : ")
            cfg["proxy"]["user"] = ask("user (blank=None) : ")
            if cfg["proxy"]["user"]:
                cfg["proxy"]["pass"] = ask("password          : ")
            else:
                cfg["proxy"]["user"] = ""
                cfg["proxy"]["pass"] = ""
            cfg["proxy"]["enabled"] = True
            ok("proxy saved")
            p.save_cfg(cfg)
            test_network()
        elif c == "2":
            if not cfg["proxy"].get("host"):
                warn("no proxy configured yet")
            else:
                cfg["proxy"]["enabled"] = not cfg["proxy"].get("enabled", False)
                ok("proxy enabled = " + str(cfg["proxy"]["enabled"]))
        elif c == "3":
            cfg["proxy"] = {"enabled": False, "host": "", "port": "", "user": "", "pass": ""}
            ok("proxy cleared")
        elif c == "0":
            p.save_cfg(cfg)
            return
        else:
            warn("unknown input")
        if c != "1":
            p.save_cfg(cfg)


def show_fingerprint(fp: dict, cfg: dict):
    dbl()
    info("active fingerprint  [profile: " + fp["profile"] + "]")
    rows = [
        ("hardwareConcurrency", fp["hardware"]["hardwareConcurrency"]),
        ("deviceMemory", fp["hardware"]["deviceMemory"]),
        ("platform", fp["hardware"]["platform"]),
        ("navigator.vendor", fp["hardware"]["vendor"]),
        ("WebGL UNMASKED_VENDOR", fp["webgl"]["vendor"]),
        ("WebGL UNMASKED_RENDERER", fp["webgl"]["renderer"]),
        ("screen", "%sx%s  avail %sx%s  dpr %s" % (fp["screen"]["width"], fp["screen"]["height"],
                                                   fp["screen"]["availWidth"], fp["screen"]["availHeight"],
                                                   fp["screen"]["devicePixelRatio"])),
        ("language(s)", ", ".join(fp["identity"]["languages"])),
        ("timezone", fp["identity"]["timezone"]),
        ("proxy", ("http://%s:%s" % (cfg["proxy"]["host"], cfg["proxy"]["port"]))
                  if cfg["proxy"].get("enabled") else "(direct)"),
        ("canvas seed", fp["seeds"]["canvas"]),
        ("canvas stride / bias", "%s  /  %s" % (fp["noise"]["canvasDensity"], fp["noise"]["canvasBias"])),
        ("webgl seed", fp["seeds"]["webgl"]),
        ("audio seed", fp["seeds"]["audio"]),
        ("misc seed", fp["seeds"]["misc"]),
    ]
    for k, v in rows:
        print("   " + Fore.LIGHTCYAN_EX + k.ljust(28) + Style.RESET_ALL + " : " + Fore.LIGHTGREEN_EX + str(v))
    dbl()


def main_menu():
    current_profile()
    while True:
        clear()
        banner()
        fp = current_profile().fingerprint()
        cfg = current_profile().config()
        show_fingerprint(fp, cfg)
        st = load_state().get("purge_targets") or []
        print(Fore.WHITE + "  purge targets : " + Fore.LIGHTGREEN_EX + (", ".join(st) if st else "(default set)"))
        hr()
        print(Fore.WHITE + "   [1] deploy fingerprint (rotate seeds)   ",
              Fore.WHITE + "     [5] autopilot reset + launch")
        print(Fore.WHITE + "   [2] deep cache purge                    ",
              Fore.WHITE + "     [0] exit")
        print(Fore.WHITE + "   [3] network / TLS masking")
        print(Fore.WHITE + "   [4] launch isolated chromium")
        print(Fore.WHITE)
        c = ask(Fore.LIGHTMAGENTA_EX + "> " + Style.RESET_ALL)
        if c == "1":
            deploy_fingerprint()
            ask(Fore.LIGHTCYAN_EX + "enter to continue...")
        elif c == "2":
            deep_purge()
            ask(Fore.LIGHTCYAN_EX + "enter to continue...")
        elif c == "3":
            configure_proxy()
        elif c == "4":
            fresh = ask("fresh temp user-data (wiped on close) ? [y/N] : ").lower().startswith("y")
            launch_menu(fresh)
        elif c == "5":
            autopilot()
        elif c == "0":
            ok("bye")
            return
        else:
            warn("unknown option")


def deploy_fingerprint():
    p = current_profile()
    fp = p.fingerprint()
    warn("current seeds: " + json.dumps(fp["seeds"]))
    if ask("rotate to new seeds ? [y/N] : ").lower().startswith("y"):
        fp = new_fingerprint(p.name)
        p.save_fp(fp)
        ok("new seeded fingerprint saved")
    show_fingerprint(fp, p.config())
    ok("browser will inject this profile on next launch (menu 4 / 5)")


def launch_menu(fresh: bool):
    p = pick_profile()
    fp = p.fingerprint()
    cfg = p.config()
    hr()
    info("launching %s chromium  [profile: %s]" % ("FRESH-TEMP" if fresh else "PERSISTENT", p.name))
    if not fresh:
        info("persistent mode: log in once, the session survives restarts")
    if not ask("continue ? [Y/n] : ").lower().startswith("n"):
        launch_browser(fp, cfg, fresh=fresh)


def autopilot():
    hr()
    info("AUTOPILOT  ->  purge + rotate + secure launch")
    ok("1/4  terminating external browsers (chrome/edge/firefox)...")
    kill_browser_procs()
    ok("2/4  deep system & browser cache purge...")
    deep_purge(quiet=True)
    ok("3/4  rotating fingerprint seeds...")
    p = current_profile()
    fp = new_fingerprint(p.name)
    p.save_fp(fp)
    show_fingerprint(fp, p.config())
    ok("4/4  secure isolated launch")
    launch_browser(fp, cfg=p.config(), fresh=True)
    ask(Fore.LIGHTCYAN_EX + "enter to continue...")


if __name__ == "__main__":
    if os.name == "nt":
        os.system("chcp 65001 >nul")
    try:
        main_menu()
    except KeyboardInterrupt:
        print()
        ok("interrupted - bye")
        sys.exit(0)
    except Exception:
        import traceback
        err("unexpected fatal error")
        err(traceback.format_exc())
        logline("FATAL:\n" + traceback.format_exc())
        ask(Fore.LIGHTCYAN_EX + "enter to exit...")
        sys.exit(1)
