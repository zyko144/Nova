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
    readonly Dictionary<string,(CoreWebView2PermissionRequestedEventArgs Args,CoreWebView2Deferral Deferral)> permissions=new();
    readonly Dictionary<string,(CoreWebView2DownloadStartingEventArgs Args,CoreWebView2Deferral Deferral)> downloadRequests=new();
    readonly Dictionary<string,CoreWebView2DownloadOperation> downloads=new();
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
        noAdblock = args.Contains("--no-adblock");privateMode=args.Contains("--private");
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
                if (File.Exists(Path.Combine(extensionPath,"manifest.json")))
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
            web.CoreWebView2.ContextMenuRequested += (_, e) => {
                e.Handled=true;
                var menu=new ContextMenuStrip { BackColor=Color.FromArgb(16,11,25),ForeColor=Color.FromArgb(226,214,240), ShowImageMargin=false, Padding=new Padding(6),Font=new Font("Segoe UI",9),Renderer=new NovaMenuRenderer() };
                void Add(string title,Action callback) { var item=new ToolStripMenuItem(title) { Padding=new Padding(10,5,10,5) };item.Click+=(_,_)=>callback();menu.Items.Add(item); }
                var link=e.ContextMenuTarget.LinkUri;
                if(!string.IsNullOrEmpty(link) && SafeUrl(link)) {
                    Add("Ouvrir dans un nouvel onglet",()=>Send(new { type="open-tab",value=link }));
                    Add("Copier l’adresse du lien",()=>Send(new {type="copy-link",value=link}));menu.Items.Add(new ToolStripSeparator());
                }
                    Add("Retour",()=>{ if(web.CanGoBack)web.GoBack();else Send(new {type="back-home"}); });
                Add("Suivant",()=>{ if(web.CanGoForward)web.GoForward(); });
                Add("Actualiser",()=>web.Reload());
                if(!string.IsNullOrEmpty(e.ContextMenuTarget.SelectionText))Add("Copier la sélection",()=>Clipboard.SetText(e.ContextMenuTarget.SelectionText));
                if(e.ContextMenuTarget.IsEditable)Add("Coller",()=>web.CoreWebView2.ExecuteScriptAsync("document.execCommand('paste')"));
                menu.Items.Add(new ToolStripSeparator());
                Add("Capture de la page",()=>Send(new {type="shortcut",value="capture"}));
                Add("Protection du site",()=>Send(new {type="shortcut",value="site"}));
                Add("Traduire en français",()=>Send(new {type="translate",value=e.ContextMenuTarget.SelectionText??""}));
                Add("Paramètres Nova",()=>Send(new {type="open-settings"}));
                Add("Réglages du bloqueur",()=>{if(blockerId.Length>0)web.CoreWebView2.Navigate("chrome-extension://"+blockerId+"/dashboard.html");});
                menu.Closed+=(_,_)=>menu.Dispose();menu.Show(web,e.Location);
            };
            web.CoreWebView2.PermissionRequested+=(_,e)=>{
                e.SavesInProfile=false;
                if(e.PermissionKind==CoreWebView2PermissionKind.ClipboardRead){e.State=CoreWebView2PermissionState.Deny;Send(new {type="security",message="Lecture automatique du presse-papiers bloquée"});return;}
                var deferral=e.GetDeferral();string id=Guid.NewGuid().ToString("N");permissions[id]=(e,deferral);
                Send(new {type="permission",id,origin=e.Uri,kind=e.PermissionKind.ToString()});
                var timeout=new System.Windows.Forms.Timer{Interval=60000};timeout.Tick+=(_,_)=>{timeout.Stop();timeout.Dispose();if(permissions.Remove(id,out var pending)){pending.Args.State=CoreWebView2PermissionState.Deny;pending.Deferral.Complete();}};timeout.Start();
            };
            web.CoreWebView2.DownloadStarting+=(_,e)=>{
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
        using var doc=JsonDocument.Parse(json);if(!downloads.TryGetValue(doc.RootElement.GetProperty("id").GetString()??"",out var op))return;
        string action=doc.RootElement.GetProperty("action").GetString()??"";
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
    protected override void OnRenderMenuItemBackground(ToolStripItemRenderEventArgs e)
    {
        using var brush=new SolidBrush(e.Item.Selected?Color.FromArgb(40,23,61):Color.FromArgb(16,11,25));
        e.Graphics.FillRectangle(brush,new Rectangle(Point.Empty,e.Item.Size));
    }
    protected override void OnRenderToolStripBorder(ToolStripRenderEventArgs e)
    {
        using var pen=new Pen(Color.FromArgb(53,32,72));e.Graphics.DrawRectangle(pen,0,0,e.ToolStrip.Width-1,e.ToolStrip.Height-1);
    }
}
