import os
import shutil
import socket

try:
    import toml
except ImportError:
    import tomllib as toml
from loguru import logger

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
config_file = f"{root_dir}/config.toml"


def load_config():
    # fix: IsADirectoryError: [Errno 21] Is a directory: '/MoneyPrinterTurbo/config.toml'
    if os.path.isdir(config_file):
        shutil.rmtree(config_file)

    if not os.path.isfile(config_file):
        example_file = f"{root_dir}/config.example.toml"
        if os.path.isfile(example_file):
            shutil.copyfile(example_file, config_file)
            logger.info("copy config.example.toml to config.toml")

    logger.info(f"load config from file: {config_file}")

    try:
        if hasattr(toml, "loads"):
            with open(config_file, mode="rb") as fp:
                _cfg_bytes = fp.read()
            try:
                _config_ = toml.loads(_cfg_bytes.decode("utf-8"))
            except Exception:
                _config_ = toml.load(config_file)
        else:
            with open(config_file, mode="rb") as fp:
                _config_ = toml.load(fp)
    except Exception as e:
        logger.warning(f"load config failed: {str(e)}, try to load as utf-8-sig")
        try:
            with open(config_file, mode="r", encoding="utf-8-sig") as fp:
                _cfg_content = fp.read()
                _config_ = toml.loads(_cfg_content)
        except Exception:
            _config_ = {}
    return _config_


def save_config():
    with open(config_file, "w", encoding="utf-8") as f:
        _cfg["app"] = app
        _cfg["azure"] = azure
        _cfg["siliconflow"] = siliconflow
        _cfg["fishspeech"] = fishspeech
        _cfg["ui"] = ui
        f.write(toml.dumps(_cfg))


_cfg = load_config()
app = _cfg.get("app", {})
if os.getenv("VOICE_NAME"):
    app["voice_name"] = os.getenv("VOICE_NAME")
whisper = _cfg.get("whisper", {})
proxy = _cfg.get("proxy", {})
azure = _cfg.get("azure", {})
siliconflow = _cfg.get("siliconflow", {})
fishspeech = _cfg.get("fishspeech", {})
ui = _cfg.get(
    "ui",
    {
        "hide_log": False,
    },
)

hostname = socket.gethostname()

log_level = _cfg.get("log_level", "DEBUG")
listen_host = _cfg.get("listen_host", "0.0.0.0")
listen_port = _cfg.get("listen_port", 8080)
project_name = _cfg.get("project_name", "MoneyPrinterTurbo")
project_description = _cfg.get(
    "project_description",
    "<a href='https://github.com/harry0703/MoneyPrinterTurbo'>https://github.com/harry0703/MoneyPrinterTurbo</a>",
)
project_version = _cfg.get("project_version", "1.2.8")
reload_debug = False

app["redis_host"] = os.getenv(
    "MPT_APP_REDIS_HOST",
    os.getenv("REDIS_HOST", app.get("redis_host", "localhost")),
)

# Cloud / GitHub Actions Environment Overrides
if os.getenv("GEMINI_API_KEY"):
    app["gemini_api_key"] = os.getenv("GEMINI_API_KEY")
    if not os.getenv("LLM_PROVIDER"):
        app["llm_provider"] = "gemini"

if os.getenv("LLM_PROVIDER"):
    app["llm_provider"] = os.getenv("LLM_PROVIDER")

if os.getenv("GEMINI_MODEL_NAME"):
    app["gemini_model_name"] = os.getenv("GEMINI_MODEL_NAME")
elif app.get("gemini_model_name") in ["gemini-pro", "gemini-1.0-pro", "gemini-2.5-flash", "gemini-flash-latest"]:
    app["gemini_model_name"] = "gemini-flash-lite-latest"

if os.getenv("PEXELS_API_KEY"):
    app["pexels_api_keys"] = [os.getenv("PEXELS_API_KEY")]

# GitHub publisher config overrides
if "github" not in _cfg:
    _cfg["github"] = {}
if os.getenv("GITHUB_TOKEN"):
    _cfg["github"]["token"] = os.getenv("GITHUB_TOKEN")
    app["github_token"] = os.getenv("GITHUB_TOKEN")
if os.getenv("GITHUB_REPO"):
    _cfg["github"]["repo"] = os.getenv("GITHUB_REPO")
    app["github_repo"] = os.getenv("GITHUB_REPO")

# YouTube cloud auto-upload overrides
if os.getenv("YOUTUBE_TOKEN_EN") or os.path.exists(os.path.join(root_dir, "data", "youtube_tokens", "youtube_token_en.pickle")):
    ui["youtube_enabled"] = True
    ui["youtube_auto_upload"] = True
    ui["youtube_privacy"] = os.getenv("YOUTUBE_PRIVACY", "public")

imagemagick_path = app.get("imagemagick_path", "")
if imagemagick_path and os.path.isfile(imagemagick_path):
    os.environ["IMAGEMAGICK_BINARY"] = imagemagick_path

ffmpeg_path = app.get("ffmpeg_path", "")
if ffmpeg_path and os.path.isfile(ffmpeg_path):
    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path

logger.info(f"{project_name} v{project_version} [LLM: {app.get('llm_provider', 'none')}]")
