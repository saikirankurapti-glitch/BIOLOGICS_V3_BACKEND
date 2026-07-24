import os

templates_dir = r"d:\Zerokost\Biologics V$$$$\frontend\templates"
target_str = '<a href="user_guide.html" class="btn-user-guide">'
inject_str = """<a href="data_registry.html" class="btn-user-guide" style="background: rgba(16, 185, 129, 0.1); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); margin-right: 0.5rem;">
                    <i class="fas fa-database"></i> Data Registry
                </a>
                <a href="user_guide.html" class="btn-user-guide">"""

sidebar_target = '<a href="data_registry.html" class="sidebar-item"><i class="fas fa-database"></i><span>Data Registry</span></a>'

for filename in os.listdir(templates_dir):
    if filename.endswith(".html"):
        filepath = os.path.join(templates_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        changed = False
        if target_str in content and 'href="data_registry.html"' not in content.split(target_str)[0][-200:]:
            content = content.replace(target_str, inject_str)
            changed = True
            
        if sidebar_target in content:
            content = content.replace(sidebar_target + "\n", "")
            content = content.replace(sidebar_target, "")
            changed = True
            
        if changed:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Updated {filename}")
