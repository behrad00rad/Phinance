Add-Type -AssemblyName System.Drawing

$iconDirectory = Join-Path $PSScriptRoot '..\frontend\public\icons'
New-Item -ItemType Directory -Force -Path $iconDirectory | Out-Null

foreach ($size in @(192, 512)) {
    $bitmap = [System.Drawing.Bitmap]::new($size, $size)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $background = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(28, 91, 67))
    $foreground = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White)
    $font = [System.Drawing.Font]::new('Arial', [float]($size * 0.49), [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
    $format = [System.Drawing.StringFormat]::new()
    try {
        $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
        $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
        $graphics.FillRectangle($background, 0, 0, $size, $size)
        $format.Alignment = [System.Drawing.StringAlignment]::Center
        $format.LineAlignment = [System.Drawing.StringAlignment]::Center
        $rectangle = [System.Drawing.RectangleF]::new(0, [float](-$size * 0.025), $size, $size)
        $graphics.DrawString('$', $font, $foreground, $rectangle, $format)
        $bitmap.Save((Join-Path $iconDirectory "phinance-$size.png"), [System.Drawing.Imaging.ImageFormat]::Png)
    } finally {
        $format.Dispose()
        $font.Dispose()
        $foreground.Dispose()
        $background.Dispose()
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}
