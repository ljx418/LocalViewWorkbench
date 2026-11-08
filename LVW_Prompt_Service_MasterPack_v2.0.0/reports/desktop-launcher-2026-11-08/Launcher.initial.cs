using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace LVWDesktop {
 public sealed class Launcher : Form {
  static readonly string Pack = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
  const string Install = @"C:\ComfyUI-aki-v2";
  Process video;
  string session;
  volatile bool preparing;
  Label status;
  Button startVideo;

  [STAThread] public static int Main(string[] args) {
   if(args.Length == 2 && args[0] == "--self-test") return SelfTest(args[1]);
   if(args.Length == 2 && args[0] == "--verify-video") return VerifyVideo(args[1]);
   Application.EnableVisualStyles();
   Application.SetCompatibleTextRenderingDefault(false);
   Application.ThreadException += delegate(object sender, System.Threading.ThreadExceptionEventArgs error) { MessageBox.Show(error.Exception.Message,"LVW 操作未完成"); };
   Application.Run(new Launcher());
   return 0;
  }
  public Launcher() {
   Text = "LVW · 本地提示词工作台";
   ClientSize = new Size(570, 440); MinimumSize = new Size(586,479);
   StartPosition = FormStartPosition.CenterScreen;
   Font = new Font("Microsoft YaHei UI",10);
   BackColor = Color.FromArgb(243,246,250);
   try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch {}
   var title = new Label { Text="LVW 本地提示词工作台", Left=28, Top=24, Width=510, Height=40, Font=new Font(Font.FontFamily,20,FontStyle.Bold), ForeColor=Color.FromArgb(23,60,100) };
   Controls.Add(title);
   Controls.Add(new Label {Text="选择入口即可启动，无需复制或输入命令。",Left=30,Top=76,Width=510,Height=28});
   AddButton("打开图片反推工作台",116,delegate { StartImage(); });
   startVideo=AddButton("启动视频反推工作流",170,delegate { StartVideo(); });
   AddButton("打开人工验收指南",224,delegate { Open(Path.Combine(Pack,"人工验收指南.html")); });
   var workflow=AddButton("定位视频工作流文件",278,delegate {
    OpenExplorer(Path.Combine(Pack,@"LVW_V0_RuntimePatch\workflows\video_reverse_prompt_v0.ui.json"));
   });
   workflow.Width=246;
   var output=new Button { Text="查看本轮视频文件",Left=292,Top=278,Width=246,Height=40 };
   output.Click+=delegate { if(session!=null && Directory.Exists(session)) Open(session); else MessageBox.Show(this,"尚未启动本轮视频服务。","LVW"); }; Controls.Add(output);
   status=new Label {Text="图片：启动后在页面点击“启动模型服务”。\n视频：页面打开后导入视频工作流；保留服务窗口。\n退出服务：在对应服务窗口按 Ctrl+C，无需输入命令。",Left=30,Top=334,Width=510,Height=88,ForeColor=Color.FromArgb(56,76,97)};
   Controls.Add(status);
   FormClosing+=delegate(object s,FormClosingEventArgs e) {
    if(preparing) { MessageBox.Show(this,"正在准备或等待视频服务启动，请稍候。","LVW");e.Cancel=true;return; }
    if(video!=null && !video.HasExited) {
     if(MessageBox.Show(this,"关闭启动器不会停止视频服务。请先导出人工稿，再到视频服务窗口按 Ctrl+C。仍要关闭启动器？","LVW",MessageBoxButtons.YesNo)!=DialogResult.Yes)e.Cancel=true;
    }
   };
  }
  Button AddButton(string text,int top,EventHandler click) {
   var b=new Button {Text=text,Left=30,Top=top,Width=508,Height=40,BackColor=Color.White,FlatStyle=FlatStyle.Flat};
   b.FlatAppearance.BorderColor=Color.FromArgb(197,208,224);b.Click+=click;Controls.Add(b);return b;
  }
  void UpdateStatus(string text) { if(!IsDisposed && IsHandleCreated) BeginInvoke((Action)delegate {status.Text=text;}); }
  static void Open(string target) { Process.Start(new ProcessStartInfo(target) {UseShellExecute=true}); }
  static void OpenExplorer(string path) { Process.Start("explorer.exe","/select,"+Quote(path)); }
  void StartImage() {
   try {
    string script=Path.Combine(Pack,"START_LVW.cmd");
    if(!File.Exists(script)) throw new FileNotFoundException("找不到图片启动器",script);
    var p=new ProcessStartInfo(script) {WorkingDirectory=Pack,UseShellExecute=true};
    Process.Start(p);status.Text="图片服务窗口已打开，等待浏览器页面。\n模型未运行时，请在页面点击“启动模型服务”。\n若启动失败，请保留服务窗口中的错误信息。";
   } catch(Exception e) { MessageBox.Show(this,e.Message,"图片启动失败"); }
  }
  static string Quote(string value) {
   // Windows CommandLineToArgvW escaping, including spaces, quotes and trailing backslashes.
   var b=new StringBuilder("\"");int slashes=0;
   foreach(char c in value) {
    if(c=='\\') {slashes++;continue;}
    if(c=='\"') {b.Append('\\',slashes*2+1);b.Append(c);slashes=0;continue;}
    b.Append('\\',slashes);slashes=0;b.Append(c);
   }
   b.Append('\\',slashes*2);return b.Append('"').ToString();
  }
  static string PythonPath {get{return Path.Combine(Install,@"python\python.exe");}}
  static string MainPath {get{return Path.Combine(Install,@"ComfyUI\main.py");}}
  static string FfmpegPath {get{return Path.Combine(Install,@"python\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe");}}
  static void Dependencies() {
   foreach(string f in new[]{PythonPath,MainPath,FfmpegPath,Path.Combine(Pack,@"LVW_V0_RuntimePatch\custom_nodes\lvw_v0_bridge\__init__.py")})
    if(!File.Exists(f))throw new FileNotFoundException("缺少本机依赖；启动器不会自动下载。",f);
  }
  static string Prepare() {
   string root=Path.Combine(Path.GetTempPath(),"lvw-s2-desktop-"+Guid.NewGuid().ToString("N"));
   Directory.CreateDirectory(root);
   try {
    foreach(string dir in new[]{"input","output","temp","user",@"temp\service-os"})Directory.CreateDirectory(Path.Combine(root,dir));
    CopyTree(Path.Combine(Pack,@"LVW_V0_RuntimePatch\custom_nodes\lvw_v0_bridge"),Path.Combine(root,@"custom_nodes\lvw_v0_bridge"));
    return root;
   } catch {Directory.Delete(root,true);throw;}
  }
  static void CopyTree(string source,string target) {
   if((File.GetAttributes(source)&FileAttributes.ReparsePoint)!=0)throw new IOException("扩展目录不能是链接。");
   Directory.CreateDirectory(target);
   foreach(string f in Directory.GetFiles(source)) {
    if((File.GetAttributes(f)&FileAttributes.ReparsePoint)!=0)throw new IOException("扩展文件不能是链接。");
    if(Path.GetExtension(f)!=".pyc")File.Copy(f,Path.Combine(target,Path.GetFileName(f)),false);
   }
   foreach(string d in Directory.GetDirectories(source)) if(Path.GetFileName(d)!="__pycache__")CopyTree(d,Path.Combine(target,Path.GetFileName(d)));
  }
  static bool PortOccupied() {
   foreach(var ep in System.Net.NetworkInformation.IPGlobalProperties.GetIPGlobalProperties().GetActiveTcpListeners())if(ep.Port==8191)return true;
   return false;
  }
  static ProcessStartInfo VideoInfo(string root) {
   var p=new ProcessStartInfo(PythonPath) {UseShellExecute=false,CreateNoWindow=false,WorkingDirectory=Path.GetDirectoryName(MainPath)};
   p.Arguments="-s -B "+Quote(MainPath)+" --listen 127.0.0.1 --port 8191 --base-directory "+Quote(root)+" --user-directory "+Quote(Path.Combine(root,"user"))+" --disable-auto-launch --disable-api-nodes --disable-all-custom-nodes --whitelist-custom-nodes lvw_v0_bridge";
   foreach(string key in new[]{"LVW_NATIVE_CHECKPOINT","LVW_WARM_BENCHMARK","LVW_FFPROBE_EXE","PYTHONPATH","PYTHONHOME","HTTP_PROXY","HTTPS_PROXY","ALL_PROXY"})p.EnvironmentVariables.Remove(key);
   foreach(string key in new[]{"PYTHONDONTWRITEBYTECODE","PYTHONNOUSERSITE","HF_HUB_OFFLINE","TRANSFORMERS_OFFLINE","HF_DATASETS_OFFLINE","OLLAMA_NO_CLOUD"})p.EnvironmentVariables[key]="1";
   p.EnvironmentVariables["LVW_FFMPEG_EXE"]=FfmpegPath;p.EnvironmentVariables["LVW_VIDEO_PROBE_BACKEND"]="pyav";
   p.EnvironmentVariables["NO_PROXY"]="127.0.0.1,localhost";
   string temp=Path.Combine(root,@"temp\service-os");
   p.EnvironmentVariables["TEMP"]=temp;p.EnvironmentVariables["TMP"]=temp;
   p.EnvironmentVariables["TORCH_HOME"]=Path.Combine(temp,"torch");p.EnvironmentVariables["HF_HOME"]=Path.Combine(temp,"huggingface");p.EnvironmentVariables["XDG_CACHE_HOME"]=Path.Combine(temp,"cache");
   return p;
  }
  void StartVideo() {
   if(preparing)return;
   if(video!=null && !video.HasExited) {Open("http://127.0.0.1:8191");return;}
   // Exported files belong to the user: do not delete a previous video session on restart.
   try {Dependencies();if(PortOccupied())throw new IOException("8191端口已占用。请检查原视频服务窗口；启动器不会终止未知进程。");}
   catch(Exception e) {MessageBox.Show(this,e.Message,"视频启动失败");return;}
   preparing=true;startVideo.Enabled=false;status.Text="正在准备临时视频环境……\n不会下载或复制模型，不修改常驻ComfyUI。";
   ThreadPool.QueueUserWorkItem(delegate {
    try {
     session=Prepare();
     File.WriteAllText(Path.Combine(session,"LVW-SESSION.txt"),"LVW desktop video session\r\nExport work before cleanup. This folder is intentionally retained.\r\n",Encoding.UTF8);
     video=Process.Start(VideoInfo(session));
     bool ready=false;
     for(int i=0;i<120;i++) {
      if(video.HasExited)throw new IOException("视频服务提前退出。请查看服务窗口；诊断目录："+session);
      try {
       var request=(HttpWebRequest)WebRequest.Create("http://127.0.0.1:8191/object_info/LVWVideoPromptOwner");request.Proxy=null;request.Timeout=700;
       using(var response=request.GetResponse())using(var stream=new StreamReader(response.GetResponseStream()))
        ready=stream.ReadToEnd().Contains("LVWVideoPromptOwner");
       if(ready)break;
      }catch(WebException){}
      Thread.Sleep(1000);
     }
     if(!ready)throw new IOException("等待视频服务超过120次探测，尚未确认就绪。服务未被强行终止，请查看其窗口。");
     UpdateStatus("视频节点已就绪，正在打开页面。\n点击“定位视频工作流文件”，将该JSON拖入视频页面。\n停止前先导出；本轮文件保留，可点“查看本轮视频文件”。");
     Open("http://127.0.0.1:8191");
    }catch(Exception e) {UpdateStatus("视频启动未完成："+e.Message);}
    finally {preparing=false;if(!IsDisposed && IsHandleCreated)BeginInvoke((Action)delegate{startVideo.Enabled=true;});}
   });
  }
  static string Hash(string f) {using(var h=SHA256.Create())using(var s=File.OpenRead(f))return BitConverter.ToString(h.ComputeHash(s)).Replace("-","").ToLowerInvariant();}
  static void Assert(bool ok,string message) {if(!ok)throw new Exception(message);}
  static int SelfTest(string receipt) {
   string root=null;
   try {
    Dependencies();
    Application.EnableVisualStyles();
    using(var form=new Launcher()) {
     Assert(form.Controls.Count>=8,"launcher controls missing");
     using(var bitmap=new Bitmap(form.Width,form.Height)) {form.DrawToBitmap(bitmap,new Rectangle(0,0,form.Width,form.Height));bitmap.Save(Path.Combine(Path.GetDirectoryName(receipt),"launcher-preview.png"));}
    }
    Assert(Quote(@"C:\中文 space\")=="\"C:\\中文 space\\\\\"","trailing-slash quoting");
    Assert(Quote("a\"b")=="\"a\\\"b\"","quote escaping");
    root=Prepare();int count=0;
    string source=Path.Combine(Pack,@"LVW_V0_RuntimePatch\custom_nodes\lvw_v0_bridge");
    string target=Path.Combine(root,@"custom_nodes\lvw_v0_bridge");
    foreach(string f in Directory.GetFiles(target,"*",SearchOption.AllDirectories)) {
     string rel=f.Substring(target.Length+1);Assert(Hash(f)==Hash(Path.Combine(source,rel)),"source hash mismatch");count++;
    }
    Assert(count>0,"no extension files");
    var p=VideoInfo(root);Assert(!p.UseShellExecute && p.Arguments.Contains("--listen 127.0.0.1") && p.Arguments.Contains("--disable-api-nodes"),"loopback flags");
    Assert(p.EnvironmentVariables["HF_HUB_OFFLINE"]=="1" && p.EnvironmentVariables["LVW_VIDEO_PROBE_BACKEND"]=="pyav","offline env");
    Assert(!File.Exists(Path.Combine(target,"__pycache__")),"cache copied");
    Directory.Delete(root,true);Assert(!Directory.Exists(root),"temporary cleanup");root=null;
    File.WriteAllText(receipt,"{\"decision\":\"LAUNCHER_SELF_TEST_PASSED_NOT_PRODUCT_ACCEPTANCE\",\"copied_files\":"+count+",\"dependencies_exist\":true,\"hashes_match\":true,\"temporary_cleanup\":true,\"product_services_started\":0,\"model_calls\":0,\"visible_browser_starts\":0}",Encoding.UTF8);
    return 0;
   } catch(Exception e) {
    if(root!=null && Directory.Exists(root))Directory.Delete(root,true);
    File.WriteAllText(receipt,"FAIL: "+e,Encoding.UTF8);return 1;
   }
  }
  static int VerifyVideo(string receipt) {
   string root=null;Process owned=null;bool ready=false,exited=true,cleaned=true;string error="";
   var log=new StringBuilder();
   try {
    Dependencies();if(PortOccupied())throw new IOException("8191 occupied: no foreign process will be touched.");
    root=Prepare();var info=VideoInfo(root);info.CreateNoWindow=true;info.RedirectStandardOutput=true;info.RedirectStandardError=true;
    owned=new Process {StartInfo=info};
    DataReceivedEventHandler collect=delegate(object s,DataReceivedEventArgs e){if(e.Data!=null)lock(log){if(log.Length<1000000)log.AppendLine(e.Data);}};
    owned.OutputDataReceived+=collect;owned.ErrorDataReceived+=collect;
    Assert(owned.Start(),"native process not started");exited=false;owned.BeginOutputReadLine();owned.BeginErrorReadLine();
    for(int i=0;i<90;i++) {
     if(owned.HasExited)throw new IOException("Comfy exited before readiness.");
     try {
      var req=(HttpWebRequest)WebRequest.Create("http://127.0.0.1:8191/object_info/LVWVideoPromptOwner");req.Proxy=null;req.Timeout=700;
      using(var response=req.GetResponse())using(var reader=new StreamReader(response.GetResponseStream()))ready=reader.ReadToEnd().Contains("LVWVideoPromptOwner");
      if(ready)break;
     }catch(WebException){}
     Thread.Sleep(1000);
    }
    Assert(ready,"native video node did not become ready");
   }catch(Exception e){error=e.GetType().Name+": "+e.Message;}
   finally {
    // No jobs/media/model requests are submitted: only the original owned idle server handle is stopped.
    if(owned!=null) {try{if(!owned.HasExited)owned.Kill();owned.WaitForExit();exited=owned.HasExited;}catch(Exception e){error+="; cleanup: "+e.Message;}}
    if(root!=null) {try{if(exited)Directory.Delete(root,true);cleaned=!Directory.Exists(root);}catch(Exception e){cleaned=false;error+="; temp: "+e.Message;}}
    lock(log)File.WriteAllText(Path.Combine(Path.GetDirectoryName(receipt),"native-video.log"),log.ToString(),Encoding.UTF8);
   }
   bool pass=ready && exited && cleaned && error=="";
   string result="{\"decision\":\""+(pass?"LAUNCHER_NATIVE_START_VERIFIED_NOT_STAGE_ACCEPTANCE":"NO_GO")+"\",\"node_registered\":"+ready.ToString().ToLower()+",\"owned_process_terminal\":"+exited.ToString().ToLower()+",\"owned_temp_removed\":"+cleaned.ToString().ToLower()+",\"product_services_started\":"+(owned==null?"0":"1")+",\"model_calls\":0,\"media_reads\":0,\"visible_browser_starts\":0}";
   File.WriteAllText(receipt,result,Encoding.UTF8);
   if(error!="")File.WriteAllText(receipt+".error.txt",error,Encoding.UTF8);
   return pass?0:1;
  }
 }
}
