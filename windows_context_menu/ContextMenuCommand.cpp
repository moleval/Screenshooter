#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shobjidl.h>
#include <shlwapi.h>
#include <shellapi.h>
#include <new>
#include <string>

#pragma comment(lib, "shlwapi.lib")

// Keep this CLSID in sync with Package.appxmanifest.
static const CLSID CLSID_ScreenshooterExplorerCommand =
{ 0x2e50e830, 0x88f2, 0x4a3a, { 0x9a, 0x6c, 0x6a, 0x31, 0x8c, 0x72, 0x44, 0x10 } };

static HMODULE g_module = nullptr;
static long g_objectCount = 0;

static HRESULT CopyString(const wchar_t* value, PWSTR* result)
{
    if (!result) return E_POINTER;
    *result = nullptr;
    const size_t bytes = (wcslen(value) + 1) * sizeof(wchar_t);
    auto buffer = static_cast<PWSTR>(CoTaskMemAlloc(bytes));
    if (!buffer) return E_OUTOFMEMORY;
    memcpy(buffer, value, bytes);
    *result = buffer;
    return S_OK;
}

static HRESULT GetSelectedPath(IShellItemArray* items, std::wstring& path)
{
    if (!items) return E_INVALIDARG;

    DWORD count = 0;
    HRESULT hr = items->GetCount(&count);
    if (FAILED(hr) || count == 0) return E_INVALIDARG;

    IShellItem* item = nullptr;
    hr = items->GetItemAt(0, &item);
    if (FAILED(hr)) return hr;

    PWSTR displayName = nullptr;
    hr = item->GetDisplayName(SIGDN_FILESYSPATH, &displayName);
    item->Release();
    if (FAILED(hr)) return hr;

    path.assign(displayName);
    CoTaskMemFree(displayName);
    return S_OK;
}

static HRESULT LaunchScreenshooter(const std::wstring& imagePath)
{
    wchar_t modulePath[MAX_PATH] = {};
    if (!GetModuleFileNameW(g_module, modulePath, MAX_PATH))
        return HRESULT_FROM_WIN32(GetLastError());

    if (PathRemoveFileSpecW(modulePath) == FALSE)
        return HRESULT_FROM_WIN32(ERROR_PATH_NOT_FOUND);

    if (!PathAppendW(modulePath, L"Screenshooter.exe"))
        return HRESULT_FROM_WIN32(ERROR_BUFFER_OVERFLOW);

    if (GetFileAttributesW(modulePath) == INVALID_FILE_ATTRIBUTES)
        return HRESULT_FROM_WIN32(ERROR_FILE_NOT_FOUND);

    SHELLEXECUTEINFOW info = {};
    info.cbSize = sizeof(info);
    info.fMask = SEE_MASK_FLAG_NO_UI;
    info.lpVerb = L"open";
    info.lpFile = modulePath;
    info.lpParameters = imagePath.c_str();
    info.nShow = SW_SHOWNORMAL;

    if (!ShellExecuteExW(&info))
        return HRESULT_FROM_WIN32(GetLastError());

    return S_OK;
}

class ScreenshooterCommand final : public IExplorerCommand
{
public:
    ScreenshooterCommand() { InterlockedIncrement(&g_objectCount); }
    ~ScreenshooterCommand() { InterlockedDecrement(&g_objectCount); }

    IFACEMETHODIMP QueryInterface(REFIID riid, void** object) override
    {
        if (!object) return E_POINTER;
        *object = nullptr;
        if (IsEqualIID(riid, IID_IUnknown) || IsEqualIID(riid, IID_IExplorerCommand))
            *object = static_cast<IExplorerCommand*>(this);
        if (!*object) return E_NOINTERFACE;
        AddRef();
        return S_OK;
    }

    IFACEMETHODIMP_(ULONG) AddRef() override
    {
        return static_cast<ULONG>(InterlockedIncrement(&references_));
    }

    IFACEMETHODIMP_(ULONG) Release() override
    {
        const ULONG remaining = static_cast<ULONG>(InterlockedDecrement(&references_));
        if (!remaining) delete this;
        return remaining;
    }

    IFACEMETHODIMP GetTitle(IShellItemArray*, PWSTR* title) override
    {
        return CopyString(L"Screenshooter", title);
    }

    IFACEMETHODIMP GetIcon(IShellItemArray*, PWSTR* icon) override
    {
        // The app icon is shipped beside the command DLL.
        wchar_t modulePath[MAX_PATH] = {};
        if (!GetModuleFileNameW(g_module, modulePath, MAX_PATH))
            return HRESULT_FROM_WIN32(GetLastError());
        if (PathRemoveFileSpecW(modulePath) == FALSE)
            return HRESULT_FROM_WIN32(ERROR_PATH_NOT_FOUND);
        if (!PathAppendW(modulePath, L"icon.ico"))
            return HRESULT_FROM_WIN32(ERROR_BUFFER_OVERFLOW);
        return CopyString(modulePath, icon);
    }

    IFACEMETHODIMP GetToolTip(IShellItemArray*, PWSTR* tooltip) override
    {
        if (tooltip) *tooltip = nullptr;
        return E_NOTIMPL;
    }

    IFACEMETHODIMP GetCanonicalName(GUID* name) override
    {
        if (!name) return E_POINTER;
        *name = CLSID_ScreenshooterExplorerCommand;
        return S_OK;
    }

    IFACEMETHODIMP GetState(IShellItemArray* items, BOOL, EXPCMDSTATE* state) override
    {
        if (!state) return E_POINTER;
        *state = ECS_HIDDEN;

        std::wstring path;
        if (FAILED(GetSelectedPath(items, path))) return S_OK;

        const wchar_t* extension = PathFindExtensionW(path.c_str());
        if (!extension) return S_OK;
        if (_wcsicmp(extension, L".png") == 0 ||
            _wcsicmp(extension, L".jpg") == 0 ||
            _wcsicmp(extension, L".jpeg") == 0 ||
            _wcsicmp(extension, L".bmp") == 0)
            *state = ECS_ENABLED;

        return S_OK;
    }

    IFACEMETHODIMP Invoke(IShellItemArray* items, IBindCtx*) override
    {
        std::wstring path;
        HRESULT hr = GetSelectedPath(items, path);
        if (FAILED(hr)) return hr;
        return LaunchScreenshooter(path);
    }

    IFACEMETHODIMP GetFlags(EXPCMDFLAGS* flags) override
    {
        if (!flags) return E_POINTER;
        *flags = ECF_DEFAULT;
        return S_OK;
    }

    IFACEMETHODIMP EnumSubCommands(IEnumExplorerCommand** commands) override
    {
        if (!commands) return E_POINTER;
        *commands = nullptr;
        return E_NOTIMPL;
    }

private:
    long references_ = 1;
};

class ScreenshooterClassFactory final : public IClassFactory
{
public:
    IFACEMETHODIMP QueryInterface(REFIID riid, void** object) override
    {
        if (!object) return E_POINTER;
        *object = nullptr;
        if (IsEqualIID(riid, IID_IUnknown) || IsEqualIID(riid, IID_IClassFactory))
            *object = static_cast<IClassFactory*>(this);
        if (!*object) return E_NOINTERFACE;
        AddRef();
        return S_OK;
    }

    IFACEMETHODIMP_(ULONG) AddRef() override
    {
        return static_cast<ULONG>(InterlockedIncrement(&references_));
    }

    IFACEMETHODIMP_(ULONG) Release() override
    {
        const ULONG remaining = static_cast<ULONG>(InterlockedDecrement(&references_));
        if (!remaining) delete this;
        return remaining;
    }

    IFACEMETHODIMP CreateInstance(IUnknown* outer, REFIID riid, void** object) override
    {
        if (outer) return CLASS_E_NOAGGREGATION;
        auto command = new (std::nothrow) ScreenshooterCommand();
        if (!command) return E_OUTOFMEMORY;
        HRESULT hr = command->QueryInterface(riid, object);
        command->Release();
        return hr;
    }

    IFACEMETHODIMP LockServer(BOOL lock) override
    {
        if (lock) InterlockedIncrement(&g_objectCount);
        else InterlockedDecrement(&g_objectCount);
        return S_OK;
    }

private:
    ~ScreenshooterClassFactory() = default;
    long references_ = 1;
};

extern "C" BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        g_module = instance;
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}

extern "C" __declspec(dllexport) HRESULT __stdcall DllGetClassObject(
    REFCLSID clsid, REFIID riid, void** object)
{
    if (!IsEqualCLSID(clsid, CLSID_ScreenshooterExplorerCommand))
        return CLASS_E_CLASSNOTAVAILABLE;

    auto factory = new (std::nothrow) ScreenshooterClassFactory();
    if (!factory) return E_OUTOFMEMORY;
    HRESULT hr = factory->QueryInterface(riid, object);
    factory->Release();
    return hr;
}

extern "C" __declspec(dllexport) HRESULT __stdcall DllCanUnloadNow()
{
    return InterlockedCompareExchange(&g_objectCount, 0, 0) == 0 ? S_OK : S_FALSE;
}
