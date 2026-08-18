param(
    [string]$EnvironmentName = "ai_amb"
)

conda run -n $EnvironmentName pyinstaller --noconfirm --clean GeradorRegistrosPGD.spec