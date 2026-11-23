using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;
using System.Runtime.InteropServices;
using System.Text.Json;

namespace NovaMediaHost;
static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();
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
    readonly IntPtr parent;
    readonly string profile, initialUrl;
    readonly bool probe;
    readonly bool noAdblock;
    string blockerId = "";
    CoreWebView2BrowserExtension? blocker;
    uint parentThread,ownThread;
    bool inputAttached;
    public MediaWindow(string[] args)
    {
        parent = new IntPtr(long.Parse(args[0])); profile = args[1]; initialUrl = args[2];
        probe = args.Contains("--probe");
        noAdblock = args.Contains("--no-adblock");
        FormBorderStyle = FormBorderStyle.None; ShowInTaskbar = parent == IntPtr.Zero;
        BackColor = Color.FromArgb(5, 4, 12); Controls.Add(web);
        Width = 1200; Height = 760;
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
    void Send(object value) { try { output.WriteLine(JsonSerializer.Serialize(value)); } catch { } }
    static bool SafeUrl(string url) => Uri.TryCreate(url, UriKind.Absolute, out var uri) && (uri.Scheme == "https" || uri.Scheme == "http");
    async Task Initialize()
    {
        try
        {
            var options = new CoreWebView2EnvironmentOptions { AreBrowserExtensionsEnabled = true };
            var environment = await CoreWebView2Environment.CreateAsync(null, profile, options);
            await web.EnsureCoreWebView2Async(environment);
            web.CoreWebView2.NewWindowRequested += (_, e) => { e.Handled = true; if (SafeUrl(e.Uri)) Send(new {type="open-tab",value=e.Uri}); };
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
            web.CoreWebView2.WebMessageReceived += (_,e)=>{
                try {
                    if(e.WebMessageAsJson.Length>20000)return;
                    var page=new Uri(web.CoreWebView2.Source);var sender=new Uri(e.Source);
                    if(page.Scheme!="https"||sender.GetLeftPart(UriPartial.Authority)!=page.GetLeftPart(UriPartial.Authority))return;
                    using var document=JsonDocument.Parse(e.WebMessageAsJson);var root=document.RootElement;
                    string type=root.GetProperty("type").GetString()??"";
                    string username=root.TryGetProperty("username",out var user)?user.GetString()??"":"";
                    if(username.Length>254)return;
                    string origin=page.GetLeftPart(UriPartial.Authority);
                    if(type=="nova-capture") {
                        string password=root.TryGetProperty("password",out var pwd)?pwd.GetString()??"":"";
                        if(password.Length<=4096)Send(new {type="credential-capture",origin,data=new {username,password}});
                    } else if(type=="nova-fill-request")Send(new {type="fill-request",origin,username});
                } catch { }
            };
            web.CoreWebView2.NavigationStarting += (_, e) => { if (!SafeUrl(e.Uri) && e.Uri != "about:blank" && !(blockerId.Length>0 && e.Uri.StartsWith("chrome-extension://"+blockerId+"/"))) e.Cancel = true; };
            web.CoreWebView2.SourceChanged += (_, _) => Send(new { type = "url", value = web.Source.ToString() });
            web.CoreWebView2.DocumentTitleChanged += (_, _) => Send(new { type = "title", value = web.CoreWebView2.DocumentTitle });
            web.CoreWebView2.FaviconChanged += async (_, _) => {
                try {
                    using var stream=await web.CoreWebView2.GetFaviconAsync(CoreWebView2FaviconImageFormat.Png);
                    using var memory=new MemoryStream();await stream.CopyToAsync(memory);
                    if(memory.Length<256000)Send(new {type="favicon",value=Convert.ToBase64String(memory.ToArray())});
                } catch { }
            };
            web.CoreWebView2.NavigationCompleted += (_, e) => Send(new { type = "loaded", ok = e.IsSuccess });
            web.KeyDown += (_, e) => {
                bool ctrl=e.Control,shift=e.Shift;
                string command="";
                if(ctrl && e.KeyCode==Keys.L)command="address";
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
                    Add("Copier l’adresse du lien",()=>Clipboard.SetText(link));menu.Items.Add(new ToolStripSeparator());
                }
                    Add("Retour",()=>{ if(web.CanGoBack)web.GoBack();else Send(new {type="back-home"}); });
                Add("Suivant",()=>{ if(web.CanGoForward)web.GoForward(); });
                Add("Actualiser",()=>web.Reload());
                menu.Items.Add(new ToolStripSeparator());
                Add("Paramètres Nova",()=>Send(new {type="open-settings"}));
                Add("Réglages du bloqueur",()=>{if(blockerId.Length>0)web.CoreWebView2.Navigate("chrome-extension://"+blockerId+"/dashboard.html");});
                menu.Closed+=(_,_)=>menu.Dispose();menu.Show(web,e.Location);
            };
            web.CoreWebView2.ServerCertificateErrorDetected += (_, e) => e.Action = CoreWebView2ServerCertificateErrorAction.Cancel;
            web.CoreWebView2.ContainsFullScreenElementChanged += (_, _) => Send(new { type = "fullscreen", value = web.CoreWebView2.ContainsFullScreenElement });
            if (SafeUrl(initialUrl)) web.CoreWebView2.Navigate(initialUrl);
            Send(new { type = "ready", value = environment.BrowserVersionString });
            _ = Task.Run(ReadCommands);
            if (probe) _ = Probe();
        }
        catch (Exception e)
        {
            Send(new { type = "error", value = e.Message });
            Controls.Clear(); Controls.Add(new Label { Dock = DockStyle.Fill, ForeColor = Color.White, Text = "Le moteur vidéo ne peut pas démarrer. Installez Microsoft Edge WebView2 Runtime.\n" + e.Message });
            if (probe) Close();
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
                    if (cmd == "navigate" && SafeUrl(value)) web.CoreWebView2.Navigate(value);
                    else if (cmd == "back") { if(web.CanGoBack)web.GoBack();else Send(new {type="back-home"}); }
                    else if (cmd == "forward" && web.CanGoForward) web.GoForward();
                    else if (cmd == "reload") web.Reload();
                    else if (cmd == "focus") web.Focus();
                    else if (cmd == "autofill") _=FillForm(value);
                    else if (cmd == "adblock-settings" && blockerId.Length>0) web.CoreWebView2.Navigate("chrome-extension://"+blockerId+"/dashboard.html");
                    else if (cmd == "adblock-toggle" && blocker!=null) _=ToggleBlocker(value=="on");
                    else if (cmd == "close") Close();
                }));
            }
            catch { }
        }
        if (!IsDisposed) try { BeginInvoke((Action)Close); } catch { }
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
