// Harness Launcher — 快捷打开 DeepSeek Harness Web GUI
// 行为：
//   1) 读取同目录 harness-launcher.json（可选）：{ "url": "...", "start": "..." }
//   2) 服务在线 -> 静默打开默认浏览器并退出（无窗口闪烁）
//   3) 服务不在线 -> 显示小对话框：自动轮询、立即检查、直接打开、退出；
//      配置了 start 命令时显示「启动服务并重试」
// 编译（Windows .NET Framework 4 自带 csc）：
//   csc.exe /target:winexe /optimize+ /platform:anycpu /codepage:65001 \
//     /r:System.dll /r:System.Core.dll /r:System.Windows.Forms.dll \
//     /r:System.Drawing.dll /r:System.Web.Extensions.dll /out:Harness.exe launcher.cs
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

public class Launcher : Form
{
    private string url = "http://127.0.0.1:3080";
    private string startCmd = "";
    private Label status;
    private Button btnStart;
    private Button btnCheck;
    private Button btnOpen;
    private Button btnExit;

    [STAThread]
    public static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Launcher app = new Launcher();
        app.RunApp();
    }

    private void RunApp()
    {
        string dir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        LoadConfig(Path.Combine(dir, "harness-launcher.json"));

        string[] args = Environment.GetCommandLineArgs();
        if (args.Length > 1)
        {
            string a = args[1];
            if (a.StartsWith("http://") || a.StartsWith("https://")) url = a;
        }

        // 快速路径：服务在线 -> 打开浏览器后直接退出，不显示窗口
        if (Ping(1200)) { OpenBrowser(); return; }

        // 服务未运行且配置了 start 命令：双击即自动拉起（无需点击任何按钮）
        if (startCmd != "") { RunStartCommand(); }

        BuildUi();

        if (startCmd != "")
        {
            status.Text = "服务未运行，正在自动启动 Harness…\r\n等待就绪后将自动打开浏览器。";
        }

        Thread poll = new Thread(new ThreadStart(PollLoop));
        poll.IsBackground = true;
        poll.Start();

        Application.Run(this);
    }

    private void RunStartCommand()
    {
        try
        {
            ProcessStartInfo psi = new ProcessStartInfo("cmd.exe", "/c " + startCmd);
            psi.CreateNoWindow = true;
            psi.UseShellExecute = false;
            Process.Start(psi);
        }
        catch (Exception) { }
    }

    private void LoadConfig(string path)
    {
        if (!File.Exists(path)) return;
        try
        {
            string text = File.ReadAllText(path, Encoding.UTF8);
            JavaScriptSerializer ser = new JavaScriptSerializer();
            Dictionary<string, object> map = ser.Deserialize<Dictionary<string, object>>(text);
            if (map == null) return;
            if (map.ContainsKey("url") && map["url"] != null) url = map["url"].ToString();
            if (map.ContainsKey("start") && map["start"] != null) startCmd = map["start"].ToString();
        }
        catch (Exception) { /* 配置损坏时使用默认值 */ }
    }

    private bool Ping(int ms)
    {
        try
        {
            HttpWebRequest req = (HttpWebRequest)WebRequest.Create(url);
            req.Method = "GET";
            req.Timeout = ms;
            req.ReadWriteTimeout = ms;
            req.AllowAutoRedirect = true;
            using (HttpWebResponse resp = (HttpWebResponse)req.GetResponse()) { return true; }
        }
        catch (WebException we)
        {
            // 拿到了 HTTP 响应（如 4xx/5xx）说明端口上有服务
            return we.Response != null;
        }
        catch (Exception) { return false; }
    }

    private void OpenBrowser()
    {
        try
        {
            Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
        }
        catch (Exception) { }
    }

    private void PollLoop()
    {
        // 自动拉起 WSL + dsh web 通常需要 30-60 秒，给 90 秒余量
        DateTime deadline = DateTime.Now.AddSeconds(90);
        while (DateTime.Now < deadline)
        {
            if (Ping(1200))
            {
                OpenBrowser();
                try { BeginInvoke(new Action(Close)); } catch (Exception) { }
                return;
            }
            Thread.Sleep(1500);
        }
        try
        {
            BeginInvoke(new Action(delegate()
            {
                status.Text = "未能连接到 " + url + "\r\n请启动 Harness 服务后点击「立即检查」。";
            }));
        }
        catch (Exception) { }
    }

    private void BuildUi()
    {
        Text = "Harness Launcher";
        ClientSize = new Size(440, 150);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        ShowInTaskbar = true;
        StartPosition = FormStartPosition.CenterScreen;
        Font = new Font("Segoe UI", 9F);

        status = new Label();
        status.SetBounds(16, 16, 408, 52);
        status.AutoSize = false;
        status.Text = "正在连接 " + url + "…\r\nHarness 服务就绪后将自动打开浏览器。";
        Controls.Add(status);

        int y = 88;
        btnExit = new Button();
        btnExit.SetBounds(352, y, 72, 32);
        btnExit.Text = "退出";
        btnExit.Click += delegate { Close(); };
        Controls.Add(btnExit);

        btnOpen = new Button();
        btnOpen.SetBounds(268, y, 84, 32);
        btnOpen.Text = "直接打开";
        btnOpen.Click += delegate { OpenBrowser(); Close(); };
        Controls.Add(btnOpen);

        btnCheck = new Button();
        btnCheck.SetBounds(176, y, 92, 32);
        btnCheck.Text = "立即检查";
        btnCheck.Click += delegate
        {
            status.Text = "重试中…";
            if (Ping(1200)) { OpenBrowser(); Close(); }
            else { status.Text = "仍未连通 " + url + "\r\n请确认服务已启动后再次点击。"; }
        };
        Controls.Add(btnCheck);

        if (startCmd != "")
        {
            btnStart = new Button();
            btnStart.SetBounds(16, y, 160, 32);
            btnStart.Text = "重新启动服务";
            btnStart.Click += delegate
            {
                status.Text = "已再次发起启动命令，等待服务就绪…";
                RunStartCommand();
            };
            Controls.Add(btnStart);
        }
    }
}
