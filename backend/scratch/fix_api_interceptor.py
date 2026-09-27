target = r"C:\Users\dsouz\Secure-Audit\audit-frontend\src\services\api.ts"
with open(target, "r", encoding="utf-8") as f:
    content = f.read()

old_str = "if (status === 401 || (status === 403 && typeof detail === 'string' && detail.toLowerCase().includes('deactivated'))) {"
new_str = "const isAuth = err.config?.url?.includes('/auth/');\n        if (!isAuth && (status === 401 || (status === 403 && typeof detail === 'string' && detail.toLowerCase().includes('deactivated')))) {"

if old_str in content:
    content = content.replace(old_str, new_str, 1)
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    print("Successfully patched api.ts!")
else:
    print("Could not find old_str in content!")
