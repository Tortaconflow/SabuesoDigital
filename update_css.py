import re

with open('C:/Users/user/.gemini/antigravity/scratch/prospector/static/css/style.css', 'r', encoding='utf-8') as f:
    css = f.read()

# 1. Spring Animations
css = re.sub(r'--transition:\s*[^;]+;', '--transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);\n    --transition-fast: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);', css)

# 2. Glassmorphism + Backgrounds
css = re.sub(r'--bg-surface:\s*[^;]+;', '--bg-surface: hsla(228, 20%, 12%, 0.65);', css)
css = re.sub(r'--bg-card:\s*[^;]+;', '--bg-card: hsla(228, 20%, 15%, 0.65);', css)

# Add backdrop filters
glass_elements = [
    r'\.sidebar',
    r'\.detail-panel',
    r'\.stat-card',
    r'\.api-provider-card',
    r'\.history-section',
    r'\.modal-content',
    r'\.toast'
]
for elem in glass_elements:
    pattern = r'(' + elem + r'\s*\{[^}]+)'
    css = re.sub(pattern, r'\1\n    backdrop-filter: blur(24px) saturate(180%);\n    -webkit-backdrop-filter: blur(24px) saturate(180%);', css, count=1)

# 3. Softer Geometry
css = re.sub(r'--radius-sm:\s*[^;]+;', '--radius-sm: 12px;', css)
css = re.sub(r'--radius-md:\s*[^;]+;', '--radius-md: 16px;', css)
css = re.sub(r'--radius-lg:\s*[^;]+;', '--radius-lg: 24px;', css)

# 4. Borders
css = re.sub(r'--border:\s*[^;]+;', '--border: hsla(255, 255, 255, 0.08);', css)

# 5. Micro-interactions
active_states = '''
.btn:active, .history-chip:active, .suggestion-card:active, .stat-card:active, .pipeline-step:active {
    transform: scale(0.95);
    transition: var(--transition-fast);
}
'''
css += active_states

# 6. Typography
fonts = "'-apple-system', 'BlinkMacSystemFont', 'SF Pro Display', 'Helvetica Neue', 'sans-serif'"
css = re.sub(r'--font-primary:\s*[^;]+;', f'--font-primary: {fonts};', css)
css = re.sub(r'--font-secondary:\s*[^;]+;', f'--font-secondary: {fonts};', css)

headings = '''
h1, h2, h3, h4, h5, h6 {
    letter-spacing: -0.02em;
}
'''
css += headings

# 7. Dynamic Toasts
dynamic_island = '''
.toast-container {
    position: fixed !important;
    top: 20px !important;
    bottom: auto !important;
    right: auto !important;
    left: 50% !important;
    transform: translateX(-50%) !important;
    align-items: center;
}

.toast {
    background-color: rgba(0, 0, 0, 0.85) !important;
    border-radius: 9999px !important;
    animation: toastIn 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
}

.toast.toast-exit {
    animation: toastOut 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards !important;
}

@keyframes toastIn {
    from {
        transform: translateY(-20px) scale(0.9);
        opacity: 0;
    }
    to {
        transform: translateY(0) scale(1);
        opacity: 1;
    }
}

@keyframes toastOut {
    from {
        transform: translateY(0) scale(1);
        opacity: 1;
    }
    to {
        transform: translateY(-20px) scale(0.9);
        opacity: 0;
    }
}
'''
css += dynamic_island

with open('C:/Users/user/.gemini/antigravity/scratch/prospector/static/css/style.css', 'w', encoding='utf-8') as f:
    f.write(css)

print('Done')
