using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace NovaMediaHost;
static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();
        if(args.Length>=2 && args[0]=="--hello"){
            using var form=new Form{Opacity=0,ShowInTaskbar=false,WindowState=FormWindowState.Normal};
            form.Shown+=async(_,_)=>{
                bool verified=false;
                try{
                    var available=await Windows.Security.Credentials.UI.UserConsentVerifier.CheckAvailabilityAsync();
                    if(available==Windows.Security.Credentials.UI.UserConsentVerifierAvailability.Available){
                        var result=await Windows.Security.Credentials.UI.UserConsentVerifierInterop.RequestVerificationForWindowAsync(form.Handle,args.Length>2 && args[2]=="private"?"Accéder à la navigation privée Nova":"Déverrouiller le coffre Nova");
                        verified=result==Windows.Security.Credentials.UI.UserConsentVerificationResult.Verified;
                    }
                }catch{}
                Console.Write(verified?"VERIFIED":"UNAVAILABLE");form.Close();
            };
            Application.Run(form);return;
        }
        Application.Run(new MediaWindow(args));
    }
}
sealed class MediaWindow : Form
{
    [DllImport("user32.dll")] static extern IntPtr SetParent(IntPtr child, IntPtr parent);
    [DllImport("user32.dll")] static extern int GetWindowLong(IntPtr h, int index);
    [DllImport("user32.dll")] static extern int SetWindowLong(IntPtr h, int index, int value);
    [DllImport("user32.dll")] static extern bool GetClientRect(IntPtr h, out RECT rect);
    [DllImport("user32.dll")] static extern bool IsWindow(IntPtr h);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h,out uint process);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint first,uint second,bool attach);
    [StructLayout(LayoutKind.Sequential)] struct RECT { public int Left, Top, Right, Bottom; }
    readonly WebView2 web = new() { Dock = DockStyle.Fill, DefaultBackgroundColor=Color.FromArgb(5,4,12) };
    readonly StreamWriter output = new(Console.OpenStandardOutput()) { AutoFlush = true };
    readonly System.Windows.Forms.Timer sizeTimer = new() { Interval = 100 };
    IntPtr parent;
    readonly string profile, initialUrl;
    readonly bool probe;
    readonly bool noAdblock;
    readonly bool selfTest;
    readonly bool privateMode;
    readonly bool skipBuiltin;
    readonly string testImageUrl;
    readonly Dictionary<string,(CoreWebView2PermissionRequestedEventArgs Args,CoreWebView2Deferral Deferral)> permissions=new();
    readonly Dictionary<string,(CoreWebView2DownloadStartingEventArgs Args,CoreWebView2Deferral Deferral)> downloadRequests=new();
    readonly Dictionary<string,CoreWebView2DownloadOperation> downloads=new();
    readonly HashSet<string> imageJobs=new(),cancelledImages=new();
    readonly Dictionary<string,(CoreWebView2ContextMenuRequestedEventArgs Args,CoreWebView2Deferral Deferral)> contexts=new();
    readonly HashSet<string> trustedHosts=new(),httpHosts=new();
    readonly List<(CoreWebView2PermissionKind Kind,string Origin)> grantedPermissions=new();
    DateTime lastPopup=DateTime.MinValue;
    CoreWebView2Environment? environment;
    string blockerId = "";
    CoreWebView2BrowserExtension? blocker;
    uint parentThread,ownThread;
    bool inputAttached;
    bool suspendRequested;
    bool contentLocked;
    readonly List<Form> loginPopups=new();
    readonly Dictionary<string,Image> menuIcons=new();
    readonly List<CoreWebView2Frame> frames = new();
    const string PauseScript="(()=>{const playing=[...document.querySelectorAll('video,audio')].filter(e=>!e.paused&&!e.ended);window.__novaPausedMedia=[...new Set([...(window.__novaPausedMedia||[]).filter(e=>e.isConnected),...playing])];playing.forEach(e=>e.pause());return playing.length;})()";
    const string ResumeScript="(()=>{const media=window.__novaPausedMedia||[];window.__novaPausedMedia=[];media.filter(e=>e.isConnected).forEach(e=>{try{e.play()?.catch(()=>{});}catch{}});})()";
    void TrackFrame(CoreWebView2Frame frame)
    {
        frames.Add(frame);frame.Destroyed+=(_,_)=>frames.Remove(frame);
        frame.FrameCreated+=(_,e)=>TrackFrame(e.Frame);
    }
    public MediaWindow(string[] args)
    {
        parent = new IntPtr(long.Parse(args[0])); profile = args[1]; initialUrl = args[2];
        probe = args.Contains("--probe");selfTest=args.Contains("--self-test");
        noAdblock = args.Contains("--no-adblock");privateMode=args.Contains("--private");skipBuiltin=args.Contains("--skip-builtin");
        testImageUrl=args.FirstOrDefault(arg=>arg.StartsWith("--test-image="))?[13..]??"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=";
        if(Uri.TryCreate(initialUrl,UriKind.Absolute,out var initial))trustedHosts.Add(initial.Host);
        FormBorderStyle = FormBorderStyle.None; ShowInTaskbar = parent == IntPtr.Zero;
        BackColor = Color.FromArgb(5, 4, 12); Controls.Add(web);
        Width = 1200; Height = 760;
        if(selfTest){Opacity=0;ShowInTaskbar=false;}
        Shown += async (_, _) => await Initialize();
        if (parent != IntPtr.Zero)
        {
            parentThread=GetWindowThreadProcessId(parent,out _);ownThread=GetCurrentThreadId();
            if(parentThread!=0 && parentThread!=ownThread)inputAttached=AttachThreadInput(ownThread,parentThread,true);
            SetParent(Handle, parent);
            SetWindowLong(Handle, -16, (GetWindowLong(Handle, -16) | 0x40000000) & ~unchecked((int)0x80000000));
            sizeTimer.Tick += (_, _) => {
                if (!IsWindow(parent)) { Close(); return; }
                if (GetClientRect(parent, out var r)) {
                    var bounds=new Rectangle(0,0,r.Right,r.Bottom);
                    if(Bounds!=bounds)Bounds=bounds;
                }
            };
            sizeTimer.Start();
        }
    }
    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        sizeTimer.Stop();
        foreach(var image in menuIcons.Values)image.Dispose();menuIcons.Clear();
        if(inputAttached)AttachThreadInput(ownThread,parentThread,false);
        base.OnFormClosed(e);
    }
    protected override void WndProc(ref Message message)
    {
        const int WM_MOUSEACTIVATE=0x21;
        if(message.Msg==WM_MOUSEACTIVATE) {
            base.WndProc(ref message);
            message.Result=new IntPtr(1);
            if(web.CoreWebView2!=null)BeginInvoke((Action)(()=>web.Focus()));
            return;
        }
        base.WndProc(ref message);
    }
    Image? MenuIcon(string name)
    {
        if(menuIcons.TryGetValue(name,out var cached))return cached;
        string file=Path.Combine(AppContext.BaseDirectory,"MenuIcons",name+".png");
        if(!File.Exists(file))return null;
        using var stream=new MemoryStream(File.ReadAllBytes(file));using var source=Image.FromStream(stream);var image=new Bitmap(source);menuIcons[name]=image;return image;
    }
    void LockContent()
    {
        contentLocked=true;web.Visible=false;
        foreach(var popup in loginPopups.ToArray()){if(!popup.IsDisposed)popup.Hide();}
    }
    async Task SuspendMedia()
    {
        suspendRequested=true;
        sizeTimer.Interval=1000;
        try {
            string paused=await web.CoreWebView2.ExecuteScriptAsync(PauseScript);
            int.TryParse(paused,out int count);
            foreach(var frame in frames.ToArray()) {try {string result=await frame.ExecuteScriptAsync(PauseScript);if(int.TryParse(result,out int n))count+=n;}catch { }}
            if(count>0)Send(new {type="media-paused",count});
            if(!suspendRequested)return;
            await web.CoreWebView2.TrySuspendAsync();
            if(!suspendRequested)await ResumeMedia(false);
        } catch { }
    }
    async Task ResumeMedia(bool focus)
    {
        suspendRequested=false;bool wasLocked=contentLocked;contentLocked=false;web.Visible=true;
        if(wasLocked)foreach(var popup in loginPopups.ToArray()){if(!popup.IsDisposed)popup.Show(this);}
        sizeTimer.Interval=100;
        try {web.CoreWebView2.Resume();if(focus)web.Focus();await web.CoreWebView2.ExecuteScriptAsync(ResumeScript);foreach(var frame in frames.ToArray()){try{await frame.ExecuteScriptAsync(ResumeScript);}catch { }}}catch { }
    }
    void Send(object value) { try { output.WriteLine(JsonSerializer.Serialize(value)); } catch { } }
    static bool SafeUrl(string url) => Uri.TryCreate(url, UriKind.Absolute, out var uri) && (uri.Scheme == "https" || uri.Scheme == "http");
    async Task Initialize()
    {
        try
        {
            var options = new CoreWebView2EnvironmentOptions { AreBrowserExtensionsEnabled = true };
            environment = await CoreWebView2Environment.CreateAsync(null, profile, options);
            var controller=environment.CreateCoreWebView2ControllerOptions();controller.IsInPrivateModeEnabled=privateMode;
            await web.EnsureCoreWebView2Async(environment,controller);
            web.CoreWebView2.IsDocumentPlayingAudioChanged+=(_,_)=>Send(new {type="audible",value=web.CoreWebView2.IsDocumentPlayingAudio});
            web.CoreWebView2.FrameCreated+=(_,e)=>TrackFrame(e.Frame);
            web.CoreWebView2.NewWindowRequested += (_, e) => { e.Handled = true;
                if(e.IsUserInitiated && DateTime.UtcNow-lastPopup>TimeSpan.FromSeconds(2) && (SafeUrl(e.Uri)||e.Uri=="about:blank")){lastPopup=DateTime.UtcNow;var deferral=e.GetDeferral();_=OpenPopup(e,deferral);}
                else Send(new {type="security",message="Ouverture de fenêtre automatique ou répétée bloquée"});
            };
            try
            {
                string extensionPath = Path.Combine(AppContext.BaseDirectory,"Extensions","ubol");
                if (!skipBuiltin && File.Exists(Path.Combine(extensionPath,"manifest.json")))
                {
                    CoreWebView2BrowserExtension? extension=null;
                    string markerPath=Path.Combine(profile,"nova-blocker.json");
                    string stamp=Path.GetFullPath(extensionPath)+"|"+File.GetLastWriteTimeUtc(Path.Combine(extensionPath,"manifest.json")).Ticks;
                    try {
                        using var marker=JsonDocument.Parse(File.ReadAllText(markerPath));
                        if(marker.RootElement.GetProperty("stamp").GetString()==stamp) {
                            string? id=marker.RootElement.GetProperty("id").GetString();
                            extension=(await web.CoreWebView2.Profile.GetBrowserExtensionsAsync()).FirstOrDefault(item=>item.Id==id);
                        }
                    } catch { }
                    extension ??= await web.CoreWebView2.Profile.AddBrowserExtensionAsync(extensionPath);
                    File.WriteAllText(markerPath,JsonSerializer.Serialize(new {stamp,id=extension.Id}));
                    blocker=extension;
                    await extension.EnableAsync(!noAdblock);
                    blockerId = extension.Id;
                    Send(new { type="adblock", enabled=extension.IsEnabled, name=extension.Name, id=extension.Id });
                }
                else Send(new { type="adblock", enabled=false, name="Extension manquante" });
            }
            catch(Exception e) { Send(new { type="adblock", enabled=false, name=e.Message }); }
            web.CoreWebView2.Settings.IsWebMessageEnabled = true;
            web.CoreWebView2.Settings.AreHostObjectsAllowed = false;
            web.CoreWebView2.Settings.IsStatusBarEnabled = false;
            web.CoreWebView2.Profile.IsGeneralAutofillEnabled=false;
            web.CoreWebView2.Profile.IsPasswordAutosaveEnabled=false;
            string formScript=Path.Combine(AppContext.BaseDirectory,"autofill.js");
            if(File.Exists(formScript))await web.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(File.ReadAllText(formScript));
            string protection=Path.Combine(AppContext.BaseDirectory,"protection.js");
            if(File.Exists(protection))await web.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(File.ReadAllText(protection));
            web.CoreWebView2.WebMessageReceived += (_,e)=>{
                try {
                    if(e.WebMessageAsJson.Length>20000)return;
                    var page=new Uri(web.CoreWebView2.Source);var sender=new Uri(e.Source);
                    if(page.Scheme!="https"||sender.GetLeftPart(UriPartial.Authority)!=page.GetLeftPart(UriPartial.Authority))return;
                    using var document=JsonDocument.Parse(e.WebMessageAsJson);var root=document.RootElement;
                    string type=root.GetProperty("type").GetString()??"";
                    string username=root.TryGetProperty("username",out var user)?user.GetString()??"":"";
                    if(type=="nova-dirty"){Send(new {type="dirty",value=root.TryGetProperty("value",out var dirty)&&dirty.GetBoolean()});return;}
                    if(type=="nova-capture-state"){Send(new {type="capture-state",audio=root.GetProperty("audio").GetBoolean(),video=root.GetProperty("video").GetBoolean()});return;}
                    if(privateMode)return;
                    if(username.Length>254)return;
                    string origin=page.GetLeftPart(UriPartial.Authority);
                    if(type=="nova-capture") {
                        string password=root.TryGetProperty("password",out var pwd)?pwd.GetString()??"":"";
                        if(password.Length<=4096)Send(new {type="credential-capture",origin,data=new {username,password}});
                    } else if(type=="nova-fill-request")Send(new {type="fill-request",origin,username});
                } catch { }
            };
            web.CoreWebView2.NavigationStarting += (_, e) => {
                if (!SafeUrl(e.Uri) && e.Uri != "about:blank" && !(blockerId.Length>0 && e.Uri.StartsWith("chrome-extension://"+blockerId+"/"))) {e.Cancel=true;return;}
                if(!SafeUrl(e.Uri))return;
                var target=new Uri(e.Uri);
                if(target.Scheme=="http" && target.Host!="localhost" && target.Host!="127.0.0.1" && !httpHosts.Contains(target.Host)){e.Cancel=true;web.CoreWebView2.Navigate(new UriBuilder(target){Scheme="https",Port=target.IsDefaultPort?-1:target.Port}.Uri.ToString());return;}
                string reason=RiskReason(target);
                if(reason.Length>0 && !trustedHosts.Contains(target.Host)){e.Cancel=true;Send(new {type="security",action="navigate",url=e.Uri,message=reason});return;}
            };
            web.CoreWebView2.SourceChanged += (_, _) => Send(new { type = "url", value = web.Source.ToString() });
            web.CoreWebView2.HistoryChanged += (_, _) => Send(new { type="history",back=web.CanGoBack,forward=web.CanGoForward });
            web.CoreWebView2.DocumentTitleChanged += (_, _) => Send(new { type = "title", value = web.CoreWebView2.DocumentTitle });
            web.CoreWebView2.FaviconChanged += async (_, _) => {
                try {
                    using var stream=await web.CoreWebView2.GetFaviconAsync(CoreWebView2FaviconImageFormat.Png);
                    using var memory=new MemoryStream();await stream.CopyToAsync(memory);
                    if(memory.Length<256000)Send(new {type="favicon",value=Convert.ToBase64String(memory.ToArray())});
                } catch { }
            };
            web.CoreWebView2.NavigationCompleted += (_, e) => {Send(new { type = "loaded", ok = e.IsSuccess });if(!e.IsSuccess && web.Source?.Scheme=="https" && e.WebErrorStatus!=CoreWebView2WebErrorStatus.OperationCanceled)Send(new {type="security",action="http",url=web.Source.ToString(),message="Connexion HTTPS interrompue"});};
            web.KeyDown += (_, e) => {
                bool ctrl=e.Control,shift=e.Shift;
                string command="";
                if(ctrl && shift && e.KeyCode==Keys.N)command="private";
                else if(ctrl && shift && e.KeyCode==Keys.M)command="mute";
                else if(ctrl && shift && e.KeyCode==Keys.F)command="focus-mode";
                else if(ctrl && shift && e.KeyCode==Keys.P)command="presentation";
                else if(ctrl && shift && e.KeyCode==Keys.S)command="capture";
                else if(ctrl && e.KeyCode==Keys.L)command="address";
                else if(ctrl && e.KeyCode==Keys.T)command="new-tab";
                else if(ctrl && e.KeyCode==Keys.W)command="close-tab";
                else if(ctrl && e.KeyCode==Keys.Tab)command=shift?"previous-tab":"next-tab";
                else if(e.KeyCode==Keys.F11)command="fullscreen";
                else if(e.KeyCode==Keys.Escape && web.CoreWebView2.ContainsFullScreenElement)command="exit-fullscreen";
                if(command.Length>0) {e.Handled=true;e.SuppressKeyPress=true;Send(new {type="shortcut",value=command});}
            };
            web.CoreWebView2.ContextMenuRequested += async (_, e) => {
                var id=Guid.NewGuid().ToString("N");var deferral=e.GetDeferral();e.Handled=true;
                foreach(var pending in contexts.Values){pending.Args.SelectedCommandId=-1;pending.Deferral.Complete();}contexts.Clear();
                contexts[id]=(e,deferral);
                var target=e.ContextMenuTarget;
                string source=target.HasSourceUri?target.SourceUri:"";
                string link=target.HasLinkUri?target.LinkUri:"",selection=target.HasSelection?target.SelectionText:"",kind=target.Kind.ToString();bool editable=target.IsEditable;int x=e.Location.X,y=e.Location.Y;
                var items=e.MenuItems.Where(item=>item.Kind==CoreWebView2ContextMenuItemKind.Command).Select(item=>new {name=item.Name,command=item.CommandId,enabled=item.IsEnabled}).ToArray();
                try{string js="(()=>{const e=document.elementFromPoint("+x+","+y+");const image=e?.closest('img')||e?.closest('[data-test-id=\"pin\"]')?.querySelector('img');return image?.currentSrc||image?.src||'';})()";string found=JsonSerializer.Deserialize<string>(await web.ExecuteScriptAsync(js))??"";if(found.Length>0)source=found;}catch{}
                Send(new {type="context-menu",id,x,y,kind,link,source,selection,editable,items});
                var timeout=new System.Windows.Forms.Timer{Interval=60000};timeout.Tick+=(_,_)=>{timeout.Stop();timeout.Dispose();if(contexts.Remove(id,out var pending)){pending.Args.SelectedCommandId=-1;pending.Deferral.Complete();}};timeout.Start();
            };
            web.CoreWebView2.PermissionRequested+=(_,e)=>{
                e.SavesInProfile=false;
                if(e.PermissionKind==CoreWebView2PermissionKind.ClipboardRead){e.State=CoreWebView2PermissionState.Deny;Send(new {type="security",message="Lecture automatique du presse-papiers bloquée"});return;}
                var deferral=e.GetDeferral();string id=Guid.NewGuid().ToString("N");permissions[id]=(e,deferral);
                Send(new {type="permission",id,origin=e.Uri,kind=e.PermissionKind.ToString()});
                var timeout=new System.Windows.Forms.Timer{Interval=60000};timeout.Tick+=(_,_)=>{timeout.Stop();timeout.Dispose();if(permissions.Remove(id,out var pending)){pending.Args.State=CoreWebView2PermissionState.Deny;pending.Deferral.Complete();}};timeout.Start();
            };
            web.CoreWebView2.DownloadStarting+=(_,e)=>{
                if(selfTest){e.Handled=true;e.ResultFilePath=Path.Combine(profile,"nova-image-test.png");return;}
                e.Handled=true;var deferral=e.GetDeferral();string id=Guid.NewGuid().ToString("N");downloadRequests[id]=(e,deferral);
                Send(new {type="download-request",id,name=Path.GetFileName(e.ResultFilePath),url=e.DownloadOperation.Uri});
                var timeout=new System.Windows.Forms.Timer{Interval=60000};timeout.Tick+=(_,_)=>{timeout.Stop();timeout.Dispose();if(downloadRequests.Remove(id,out var pending)){pending.Args.Cancel=true;pending.Deferral.Complete();}};timeout.Start();
            };
            web.CoreWebView2.ServerCertificateErrorDetected += (_, e) => e.Action = CoreWebView2ServerCertificateErrorAction.Cancel;
            web.CoreWebView2.ContainsFullScreenElementChanged += (_, _) => Send(new { type = "fullscreen", value = web.CoreWebView2.ContainsFullScreenElement });
            if (SafeUrl(initialUrl)) web.CoreWebView2.Navigate(initialUrl);
            Send(new { type = "ready", value = environment.BrowserVersionString });
            if(selfTest){await SelfTest();return;}
            _ = Task.Run(ReadCommands);
            if (probe) _ = Probe();
        }
        catch (Exception e)
        {
            Send(new { type = "error", value = e.Message });
            Controls.Clear(); Controls.Add(new Label { Dock = DockStyle.Fill, ForeColor = Color.White, Text = "Le moteur vidéo ne peut pas démarrer. Installez Microsoft Edge WebView2 Runtime.\n" + e.Message });
            if (selfTest){Environment.ExitCode=2;Close();}
            else if (probe) Close();
        }
    }
    void ReadCommands()
    {
        using var reader = new StreamReader(Console.OpenStandardInput());
        string? line;
        while ((line = reader.ReadLine()) != null)
        {
            try
            {
                using var document = JsonDocument.Parse(line);
                string cmd = document.RootElement.GetProperty("command").GetString() ?? "";
                string value = document.RootElement.TryGetProperty("value", out var v) ? v.GetString() ?? "" : "";
                BeginInvoke((Action)(() => {
                    if (cmd == "navigate" && SafeUrl(value)) {trustedHosts.Add(new Uri(value).Host);web.CoreWebView2.Navigate(value);}
                    else if (cmd == "back") { if(web.CanGoBack)web.GoBack();else Send(new {type="back-home"}); }
                    else if (cmd == "forward" && web.CanGoForward) web.GoForward();
                    else if(cmd=="exit-fullscreen")_=web.ExecuteScriptAsync("if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});");
                    else if (cmd == "reload") web.Reload();
                    else if (cmd == "focus") web.Focus();
                    else if (cmd == "reparent" && long.TryParse(value,out long handle)) {parent=new IntPtr(handle);SetParent(Handle,parent);}
                    else if(cmd=="lock")LockContent();
                    else if (cmd == "suspend") _=SuspendMedia();
                    else if (cmd == "resume") _=ResumeMedia(value=="focus");
                    else if (cmd == "autofill") _=FillForm(value);
                    else if (cmd == "adblock-settings" && blockerId.Length>0) web.CoreWebView2.Navigate("chrome-extension://"+blockerId+"/dashboard.html");
                    else if (cmd == "adblock-toggle" && blocker!=null) _=ToggleBlocker(value=="on");
                    else if(cmd=="thumbnail")_=Thumbnail();
                    else if(cmd=="resources")SendResources();
                    else if(cmd=="mute")web.CoreWebView2.IsMuted=value=="on";
                    else if(cmd=="allow-http")httpHosts.Add(value);
                    else if(cmd=="permission-result")PermissionResult(value);
                    else if(cmd=="context-result")ContextResult(value);
                    else if(cmd=="save-image")_=SaveImage(value);
                    else if(cmd=="extensions-list")_=Extensions("list",value);
                    else if(cmd=="extensions-enable")_=Extensions("enable",value);
                    else if(cmd=="extensions-remove")_=Extensions("remove",value);
                    else if(cmd=="extensions-restore")_=Extensions("restore",value);
                    else if(cmd=="download-answer")DownloadAnswer(value);
                    else if(cmd=="download-control")DownloadControl(value);
                    else if(cmd=="capture")_=CapturePage(value);
                    else if(cmd=="script" && value.Length<20000)_=web.ExecuteScriptAsync(value);
                    else if(cmd=="revoke")_=Revoke();
                    else if(cmd=="emergency"){_=Revoke();_=web.ExecuteScriptAsync("window.__novaEmergency?.()");web.CoreWebView2.IsMuted=true;web.CoreWebView2.Stop();web.CoreWebView2.Navigate("about:blank");}
                    else if(cmd=="clear-site")_=ClearSite();
                    else if (cmd == "close") Close();
                }));
            }
            catch { }
        }
        if (!IsDisposed) try { BeginInvoke((Action)Close); } catch { }
    }
    async Task SelfTest()
    {
        try{
            if(privateMode&&!web.CoreWebView2.Profile.IsInPrivateModeEnabled)throw new InvalidOperationException("Private controller not enabled");
            await web.ExecuteScriptAsync("document.body.innerHTML='<input id=nova>';document.getElementById('nova').value='ready';document.title='Nova self test';");
            var result=await web.ExecuteScriptAsync("document.getElementById('nova').value");
            if(result!="\"ready\"")throw new InvalidOperationException("Document unavailable");
            LockContent();if(web.Visible)throw new InvalidOperationException("Locked content still visible");await ResumeMedia(false);if(!web.Visible||contentLocked)throw new InvalidOperationException("Unlock failed");
            using var stream=new MemoryStream();await web.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png,stream);
            if(stream.Length<100)throw new InvalidOperationException("Capture failed");
            await web.ExecuteScriptAsync("document.body.innerHTML='';document.body.style.margin='0';var img=document.createElement('img');img.width=100;img.height=100;img.src="+JsonSerializer.Serialize(testImageUrl)+";document.body.appendChild(img);");
            await Task.Delay(300);
            await web.CoreWebView2.CallDevToolsProtocolMethodAsync("Input.dispatchMouseEvent","{\"type\":\"mousePressed\",\"x\":40,\"y\":40,\"button\":\"right\",\"clickCount\":1}");
            await web.CoreWebView2.CallDevToolsProtocolMethodAsync("Input.dispatchMouseEvent","{\"type\":\"mouseReleased\",\"x\":40,\"y\":40,\"button\":\"right\",\"clickCount\":1}");
            for(int i=0;i<30 && contexts.Count==0;i++)await Task.Delay(100);
            if(contexts.Count==0)throw new InvalidOperationException("Image context event missing");
            var context=contexts.First();var save=context.Value.Args.MenuItems.FirstOrDefault(item=>item.Name=="saveImageAs" && item.IsEnabled);
            if(save==null)throw new InvalidOperationException("Native image save command missing");
            ContextResult(JsonSerializer.Serialize(new {id=context.Key,command=-1}));
            await SaveImage(JsonSerializer.Serialize(new {id="image-test",path=Path.Combine(profile,"nova-image-test.png"),url=testImageUrl}));
            string imagePath=Path.Combine(profile,"nova-image-test.png");
            for(int i=0;i<50 && !File.Exists(imagePath);i++)await Task.Delay(100);
            var saved=File.Exists(imagePath)?await File.ReadAllBytesAsync(imagePath):Array.Empty<byte>();
            if(saved.Length<8||saved[0]!=137||saved[1]!=80||saved[2]!=78||saved[3]!=71)throw new InvalidOperationException("Image save did not create a PNG");
            if(blocker!=null){
                string extension=blocker.Id;
                await Extensions("enable",JsonSerializer.Serialize(new {id=extension,enabled=false}));
                if((await web.CoreWebView2.Profile.GetBrowserExtensionsAsync()).First(item=>item.Id==extension).IsEnabled)throw new InvalidOperationException("Extension disable failed");
                await Extensions("enable",JsonSerializer.Serialize(new {id=extension,enabled=true}));
                if(!(await web.CoreWebView2.Profile.GetBrowserExtensionsAsync()).First(item=>item.Id==extension).IsEnabled)throw new InvalidOperationException("Extension enable failed");
                await Extensions("remove",JsonSerializer.Serialize(new {id=extension}));
                if((await web.CoreWebView2.Profile.GetBrowserExtensionsAsync()).Any(item=>item.Id==extension))throw new InvalidOperationException("Extension removal failed");
                await Extensions("restore","{}");
                if(blocker==null||!blocker.IsEnabled)throw new InvalidOperationException("Extension restore failed");
            }
            Send(new {type="self-test",ok=true,privateMode});
        }catch(Exception error){Send(new {type="self-test",ok=false,error=error.Message});Environment.ExitCode=2;}
        Close();
    }
    void SendResources()
    {
        long memory=0;try{foreach(var info in environment!.GetProcessInfos()){if(info.Kind==CoreWebView2ProcessKind.Renderer){try{using var process=System.Diagnostics.Process.GetProcessById(info.ProcessId);memory+=process.WorkingSet64;}catch{}}}}catch{}
        Send(new {type="resources",memory});
    }
    async Task Thumbnail()
    {
        try{using var stream=new MemoryStream();await web.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png,stream);stream.Position=0;using var image=Image.FromStream(stream);using var thumb=new Bitmap(280,160);using(var graphics=Graphics.FromImage(thumb)){graphics.Clear(Color.FromArgb(12,12,12));graphics.DrawImage(image,new Rectangle(0,0,280,160));}using var output=new MemoryStream();thumb.Save(output,System.Drawing.Imaging.ImageFormat.Png);if(output.Length<256000)Send(new {type="thumbnail",value=Convert.ToBase64String(output.ToArray())});}catch{}
    }
    async Task OpenPopup(CoreWebView2NewWindowRequestedEventArgs request,CoreWebView2Deferral deferral)
    {
        Form? popup=null;
        try{
            popup=new Form{Text="Connexion · Nova",Width=620,Height=760,BackColor=Color.FromArgb(15,15,15),StartPosition=FormStartPosition.CenterParent};
            var address=new TextBox{Dock=DockStyle.Top,ReadOnly=true,BorderStyle=BorderStyle.None,BackColor=Color.FromArgb(28,28,28),ForeColor=Color.White,Text=request.Uri};
            var child=new WebView2{Dock=DockStyle.Fill,DefaultBackgroundColor=Color.FromArgb(15,15,15)};popup.Controls.Add(child);popup.Controls.Add(address);
            var controller=environment!.CreateCoreWebView2ControllerOptions();controller.IsInPrivateModeEnabled=privateMode;
            await child.EnsureCoreWebView2Async(environment,controller);
            child.CoreWebView2.Settings.AreHostObjectsAllowed=false;child.CoreWebView2.Profile.IsPasswordAutosaveEnabled=false;child.CoreWebView2.Profile.IsGeneralAutofillEnabled=false;
            child.CoreWebView2.SourceChanged+=(_,_)=>address.Text=child.Source?.ToString()??"";
            child.CoreWebView2.NavigationStarting+=(_,e)=>{if(!SafeUrl(e.Uri)&&e.Uri!="about:blank")e.Cancel=true;};
            child.CoreWebView2.ServerCertificateErrorDetected+=(_,e)=>e.Action=CoreWebView2ServerCertificateErrorAction.Cancel;
            child.CoreWebView2.PermissionRequested+=(_,e)=>{e.State=CoreWebView2PermissionState.Deny;e.SavesInProfile=false;};
            child.CoreWebView2.NewWindowRequested+=(_,e)=>e.Handled=true;
            child.CoreWebView2.WindowCloseRequested+=(_,_)=>popup.Close();
            request.NewWindow=child.CoreWebView2;loginPopups.Add(popup);popup.FormClosed+=(_,_)=>{loginPopups.Remove(popup);child.Dispose();};popup.Owner=this;if(!contentLocked)popup.Show(this);
        }catch{popup?.Dispose();Send(new {type="security",message="La fenêtre de connexion n’a pas pu s’ouvrir"});}
        finally{deferral.Complete();}
    }
    static string RiskReason(Uri uri)
    {
        string host=uri.IdnHost.ToLowerInvariant();
        string decoded=new System.Globalization.IdnMapping().GetUnicode(host);
        if(Regex.IsMatch(decoded,"[a-z]",RegexOptions.IgnoreCase)&&Regex.IsMatch(decoded,"[\u0370-\u03ff\u0400-\u04ff]"))return "Adresse mélangeant plusieurs alphabets";
        foreach(string brand in new[]{"google","youtube","gmail","discord","paypal","microsoft","netflix","apple"})if((host.Split('.')[0].Contains(brand)||host.StartsWith(brand+".")) && host!=brand+".com" && !host.EndsWith("."+brand+".com"))return "Domaine ressemblant à "+brand;
        return uri.UserInfo.Length>0?"Identifiant masquant le vrai domaine":"";
    }
    void PermissionResult(string json)
    {
        using var doc=JsonDocument.Parse(json);string id=doc.RootElement.GetProperty("id").GetString()??"";
        if(!permissions.Remove(id,out var pending))return;
        bool allow=doc.RootElement.GetProperty("allow").GetBoolean();
        pending.Args.State=allow?CoreWebView2PermissionState.Allow:CoreWebView2PermissionState.Deny;
        if(allow)grantedPermissions.Add((pending.Args.PermissionKind,pending.Args.Uri));
        pending.Deferral.Complete();
    }
    async Task Revoke()
    {
        await web.ExecuteScriptAsync("window.__novaStopCapture?.()");
        foreach(var frame in frames.ToArray()){try{await frame.ExecuteScriptAsync("window.__novaStopCapture?.()");}catch{}}
        foreach(var permission in grantedPermissions.ToArray()){try{await web.CoreWebView2.Profile.SetPermissionStateAsync(permission.Kind,permission.Origin,CoreWebView2PermissionState.Default);}catch{}}
        grantedPermissions.Clear();
    }
    async Task ClearSite()
    {
        var uri=new Uri(web.CoreWebView2.Source);var cookies=await web.CoreWebView2.CookieManager.GetCookiesAsync(uri.GetLeftPart(UriPartial.Authority));
        foreach(var cookie in cookies)web.CoreWebView2.CookieManager.DeleteCookie(cookie);
        await web.ExecuteScriptAsync("(()=>{localStorage.clear();sessionStorage.clear();caches.keys().then(k=>k.forEach(x=>caches.delete(x)));indexedDB.databases?.().then(d=>d.forEach(x=>indexedDB.deleteDatabase(x.name)));navigator.serviceWorker?.getRegistrations().then(r=>r.forEach(x=>x.unregister()));})()");
    }
    async Task CapturePage(string json)
    {
        using var doc=JsonDocument.Parse(json);string path=doc.RootElement.GetProperty("path").GetString()??"",mode=doc.RootElement.GetProperty("mode").GetString()??"visible";
        bool ok=false;try{if(mode=="pdf")ok=await web.CoreWebView2.PrintToPdfAsync(path);else{using var stream=File.Create(path);await web.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png,stream);ok=true;}}catch{}
        Send(new {type="screenshot",ok,path,mode});
    }
    void ContextResult(string json)
    {
        using var doc=JsonDocument.Parse(json);var root=doc.RootElement;
        if(!contexts.Remove(root.GetProperty("id").GetString()??"",out var pending))return;
        int command=root.GetProperty("command").GetInt32();
        pending.Args.SelectedCommandId=pending.Args.MenuItems.Any(item=>item.CommandId==command && item.IsEnabled)?command:-1;
        pending.Deferral.Complete();
    }
    async Task Extensions(string action,string json)
    {
        try{
            string builtin=blockerId;
            try{using var marker=JsonDocument.Parse(File.ReadAllText(Path.Combine(profile,"nova-blocker.json")));builtin=marker.RootElement.GetProperty("id").GetString()??builtin;}catch{}
            string affected="";bool removed=false;
            if(action=="restore"){
                string path=Path.Combine(AppContext.BaseDirectory,"Extensions","ubol");
                blocker=await web.CoreWebView2.Profile.AddBrowserExtensionAsync(path);blockerId=blocker.Id;builtin=blocker.Id;await blocker.EnableAsync(true);affected=builtin;
                string stamp=Path.GetFullPath(path)+"|"+File.GetLastWriteTimeUtc(Path.Combine(path,"manifest.json")).Ticks;File.WriteAllText(Path.Combine(profile,"nova-blocker.json"),JsonSerializer.Serialize(new {stamp,id=builtin}));
            }else if(action!="list"){
                using var doc=JsonDocument.Parse(json);affected=doc.RootElement.GetProperty("id").GetString()??"";
                var extension=(await web.CoreWebView2.Profile.GetBrowserExtensionsAsync()).FirstOrDefault(item=>item.Id==affected)??throw new IOException("Extension introuvable");
                if(action=="remove"){await extension.RemoveAsync();removed=true;if(affected==builtin){blocker=null;blockerId="";}}
                else if(action=="enable")await extension.EnableAsync(doc.RootElement.GetProperty("enabled").GetBoolean());
            }
            var installed=await web.CoreWebView2.Profile.GetBrowserExtensionsAsync();
            // WebView2 also returns its internal PDF and clipboard components;
            // those are runtime services, not user-installed extensions.
            Send(new {type="extensions-state",affected,removed,builtin,items=installed.Where(item=>item.Id!="mhjfbmdgcfjbbpaeojofohoefgiehjai" && item.Id!="dgiklkfkllikcanfonkcabmbdfmgleag").Select(item=>new {id=item.Id,name=item.Name,enabled=item.IsEnabled,builtin=item.Id==builtin}).ToArray()});
        }catch(Exception error){Send(new {type="extensions-error",message=error.Message});}
    }
    async Task<byte[]> ImageBytes(string url)
    {
        const int limit=50*1024*1024;
        if(url.StartsWith("data:image/",StringComparison.OrdinalIgnoreCase)){
            int comma=url.IndexOf(',');if(comma<0||url.Length>limit*1.4)throw new IOException("Image trop volumineuse");
            return url[..comma].EndsWith(";base64",StringComparison.OrdinalIgnoreCase)?Convert.FromBase64String(url[(comma+1)..]):System.Text.Encoding.UTF8.GetBytes(Uri.UnescapeDataString(url[(comma+1)..]));
        }
        if(!Uri.TryCreate(url,UriKind.Absolute,out var uri)||(uri.Scheme!="https"&&uri.Scheme!="http"&&uri.Scheme!="blob"))throw new IOException("Adresse d’image non prise en charge");
        using var tree=JsonDocument.Parse(await web.CoreWebView2.CallDevToolsProtocolMethodAsync("Page.getFrameTree","{}"));string frame=tree.RootElement.GetProperty("frameTree").GetProperty("frame").GetProperty("id").GetString()!;
        try{
            using var resource=JsonDocument.Parse(await web.CoreWebView2.CallDevToolsProtocolMethodAsync("Page.getResourceContent",JsonSerializer.Serialize(new {frameId=frame,url})));
            string content=resource.RootElement.GetProperty("content").GetString()??"";if(content.Length>limit*1.4)throw new IOException("Image trop volumineuse");
            return resource.RootElement.GetProperty("base64Encoded").GetBoolean()?Convert.FromBase64String(content):System.Text.Encoding.UTF8.GetBytes(content);
        }catch when(uri.Scheme!="blob"){}
        using var response=JsonDocument.Parse(await web.CoreWebView2.CallDevToolsProtocolMethodAsync("Network.loadNetworkResource",JsonSerializer.Serialize(new {frameId=frame,url,options=new {disableCache=false,includeCredentials=true}})));
        var data=response.RootElement.GetProperty("resource");if(!data.GetProperty("success").GetBoolean()||!data.TryGetProperty("stream",out var stream))throw new IOException("Le serveur n’a pas transmis l’image");
        string handle=stream.GetString()!;
        try{
            using var result=new MemoryStream();
            while(true){
                using var part=JsonDocument.Parse(await web.CoreWebView2.CallDevToolsProtocolMethodAsync("IO.read",JsonSerializer.Serialize(new {handle,size=65536})));
                string text=part.RootElement.GetProperty("data").GetString()??"";byte[] chunk=part.RootElement.TryGetProperty("base64Encoded",out var encoded)&&encoded.GetBoolean()?Convert.FromBase64String(text):System.Text.Encoding.UTF8.GetBytes(text);
                if(result.Length+chunk.Length>limit)throw new IOException("Image trop volumineuse");await result.WriteAsync(chunk);
                if(part.RootElement.GetProperty("eof").GetBoolean())break;
            }
            return result.ToArray();
        }finally{await web.CoreWebView2.CallDevToolsProtocolMethodAsync("IO.close",JsonSerializer.Serialize(new {handle}));}
    }
    async Task SaveImage(string json)
    {
        string id="",temporary="";
        try{
            using var doc=JsonDocument.Parse(json);var root=doc.RootElement;id=root.GetProperty("id").GetString()??"";string path=root.GetProperty("path").GetString()??"",url=root.GetProperty("url").GetString()??"";
            if(contentLocked||!Path.IsPathFullyQualified(path))throw new IOException("Enregistrement indisponible");
            Send(new {type="download-state",id,state="DownloadInProgress",received=0,total=0,paused=false,resumable=false});
            imageJobs.Add(id);byte[] bytes=await ImageBytes(url).WaitAsync(TimeSpan.FromSeconds(30));if(bytes.Length==0)throw new IOException("Image vide");
            if(cancelledImages.Contains(id))return;
            temporary=path+".nova-"+Guid.NewGuid().ToString("N")+".part";await File.WriteAllBytesAsync(temporary,bytes);
            if(cancelledImages.Contains(id))return;
            File.Move(temporary,path,true);temporary="";
            Send(new {type="download-state",id,state="DownloadCompleted",received=bytes.Length,total=bytes.Length,paused=false,resumable=false});
        }catch(Exception error){Send(new {type="download-state",id,state="DownloadInterrupted",received=0,total=0,paused=false,resumable=false,reason=error.Message});}
        finally{imageJobs.Remove(id);cancelledImages.Remove(id);if(temporary.Length>0)try{File.Delete(temporary);}catch{}}
    }
    void DownloadAnswer(string json)
    {
        using var doc=JsonDocument.Parse(json);string id=doc.RootElement.GetProperty("id").GetString()??"";
        if(!downloadRequests.Remove(id,out var pending))return;
        string path=doc.RootElement.GetProperty("path").GetString()??"";
        if(path.Length==0){pending.Args.Cancel=true;pending.Deferral.Complete();return;}
        pending.Args.ResultFilePath=path;var op=pending.Args.DownloadOperation;downloads[id]=op;
        void Report()=>Send(new {type="download-state",id,received=op.BytesReceived,total=op.TotalBytesToReceive,paused=op.State==CoreWebView2DownloadState.Interrupted,resumable=op.CanResume,reason=op.InterruptReason.ToString(),state=op.InterruptReason==CoreWebView2DownloadInterruptReason.UserCanceled?"DownloadCancelled":op.State==CoreWebView2DownloadState.Completed?"DownloadCompleted":op.State==CoreWebView2DownloadState.Interrupted?"DownloadInterrupted":"DownloadInProgress"});
        op.BytesReceivedChanged+=(_,_)=>Report();op.StateChanged+=(_,_)=>Report();pending.Deferral.Complete();Report();
    }
    void DownloadControl(string json)
    {
        using var doc=JsonDocument.Parse(json);string id=doc.RootElement.GetProperty("id").GetString()??"";
        string action=doc.RootElement.GetProperty("action").GetString()??"";
        if(imageJobs.Contains(id)){if(action=="cancel"){cancelledImages.Add(id);Send(new {type="download-state",id,state="DownloadCancelled",received=0,total=0,paused=false,resumable=false});}return;}
        if(!downloads.TryGetValue(id,out var op))return;
        if(action=="pause")op.Pause();else if(action=="resume" && op.CanResume)op.Resume();else if(action=="cancel")op.Cancel();
    }
    async Task FillForm(string value)
    {
        try {
            if(value.Length>20000)return;
            using var document=JsonDocument.Parse(value);
            var page=new Uri(web.CoreWebView2.Source);
            if(page.Scheme!="https"||document.RootElement.GetProperty("origin").GetString()!=page.GetLeftPart(UriPartial.Authority))return;
            await web.ExecuteScriptAsync("window.__novaFill?.("+document.RootElement.GetRawText()+")");
        } catch { }
    }
    async Task ToggleBlocker(bool enabled)
    {
        if(blocker==null)return;
        await blocker.EnableAsync(enabled);
        Send(new {type="adblock",enabled=blocker.IsEnabled,name=blocker.Name,id=blocker.Id});
    }
    async Task Probe()
    {
        await web.CoreWebView2.CallDevToolsProtocolMethodAsync("Network.enable", "{}");
        var failures = web.CoreWebView2.GetDevToolsProtocolEventReceiver("Network.loadingFailed");
        failures.DevToolsProtocolEventReceived += (_, e) => {
            if (e.ParameterObjectAsJson.Contains("ERR_BLOCKED_BY_CLIENT")) Send(new {type="filter-test",blocked=true});
        };
        await web.ExecuteScriptAsync("void fetch('https://googleads.g.doubleclick.net/pagead/id').catch(()=>{})");
        await Task.Delay(20000);
        string js = "JSON.stringify({title:document.title,codecs:['video/mp4; codecs=\"avc1.42E01E\"','audio/mp4; codecs=\"mp4a.40.2\"'].map(t=>[t,document.createElement('video').canPlayType(t)]),videos:[...document.querySelectorAll('video')].map(v=>({time:v.currentTime,ready:v.readyState,paused:v.paused,error:v.error&&v.error.message})),errors:[...document.querySelectorAll('.ytp-error-content-wrap')].map(x=>x.innerText)})";
        var pointJson = await web.ExecuteScriptAsync("(()=>{let b=document.querySelector('.ytp-play-button');if(!b)return null;let r=b.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,paused:document.querySelector('video')?.paused}})()");
        using(var point = JsonDocument.Parse(pointJson))
        {
            if(point.RootElement.ValueKind == JsonValueKind.Object && point.RootElement.GetProperty("paused").GetBoolean())
            {
                double x=point.RootElement.GetProperty("x").GetDouble(), y=point.RootElement.GetProperty("y").GetDouble();
                await web.CoreWebView2.CallDevToolsProtocolMethodAsync("Input.dispatchMouseEvent", JsonSerializer.Serialize(new { type="mousePressed", x, y, button="left", clickCount=1 }));
                await web.CoreWebView2.CallDevToolsProtocolMethodAsync("Input.dispatchMouseEvent", JsonSerializer.Serialize(new { type="mouseReleased", x, y, button="left", clickCount=1 }));
            }
        }
        await Task.Delay(6000);
        Send(new { type = "probe", value = await web.ExecuteScriptAsync(js) });
        Close();
    }
}
sealed class NovaMenuRenderer : ToolStripProfessionalRenderer
{
    static System.Drawing.Drawing2D.GraphicsPath Round(Rectangle r,int radius)
    {
        int d=radius*2;var path=new System.Drawing.Drawing2D.GraphicsPath();path.AddArc(r.Left,r.Top,d,d,180,90);path.AddArc(r.Right-d,r.Top,d,d,270,90);path.AddArc(r.Right-d,r.Bottom-d,d,d,0,90);path.AddArc(r.Left,r.Bottom-d,d,d,90,90);path.CloseFigure();return path;
    }
    public static Region CreateRegion(Size size){using var path=Round(new Rectangle(Point.Empty,size),10);return new Region(path);}
    protected override void OnRenderMenuItemBackground(ToolStripItemRenderEventArgs e)
    {
        e.Graphics.SmoothingMode=System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
        if(e.Item.Selected){using var brush=new SolidBrush(Color.FromArgb(48,48,55));using var path=Round(new Rectangle(2,1,e.Item.Width-4,e.Item.Height-2),6);e.Graphics.FillPath(brush,path);}
    }
    protected override void OnRenderImageMargin(ToolStripRenderEventArgs e)
    {using var brush=new SolidBrush(Color.FromArgb(25,25,29));e.Graphics.FillRectangle(brush,e.AffectedBounds);}
    protected override void OnRenderSeparator(ToolStripSeparatorRenderEventArgs e)
    {using var pen=new Pen(Color.FromArgb(51,51,59));e.Graphics.DrawLine(pen,10,e.Item.Height/2,e.Item.Width-10,e.Item.Height/2);}
    protected override void OnRenderToolStripBorder(ToolStripRenderEventArgs e)
    {e.Graphics.SmoothingMode=System.Drawing.Drawing2D.SmoothingMode.AntiAlias;using var pen=new Pen(Color.FromArgb(57,57,64));using var path=Round(new Rectangle(0,0,e.ToolStrip.Width-1,e.ToolStrip.Height-1),10);e.Graphics.DrawPath(pen,path);}
}
