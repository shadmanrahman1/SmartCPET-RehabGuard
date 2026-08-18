# Set environment variables for local ML caches to prevent Hugging Face/Keras from using the C: Drive
$env:HF_HOME = "F:\Skill_WORK\CODE\CPET_system\.cache\huggingface"
$env:KERAS_HOME = "F:\Skill_WORK\CODE\CPET_system\.cache\keras"
$env:XDG_CACHE_HOME = "F:\Skill_WORK\CODE\CPET_system\.cache\xdg"
$env:JUPYTER_RUNTIME_DIR = "F:\Skill_WORK\CODE\CPET_system\.cache\jupyter\runtime"
$env:JUPYTER_DATA_DIR = "F:\Skill_WORK\CODE\CPET_system\.cache\jupyter\data"

Write-Host "Set cache directories to F:\Skill_WORK\CODE\CPET_system\.cache"
