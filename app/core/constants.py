"""全局常量"""

# 上传/素材文件扩展名白名单
VIDEO_ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov"}
AUDIO_ALLOWED_EXTENSIONS = {".mp3", ".wav"}
SRT_ALLOWED_EXTENSIONS = {".srt"}

# 上传文件大小上限（MB）
MAX_UPLOAD_MB = 500

# 输出产物静态挂载 URL 前缀（与 server.py 的 mount 配对）
OUTPUT_URL_PREFIX = "/output"
