using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Text;
using System.Windows.Forms;
namespace LVWDesktop {
 public sealed class Launcher:Form {
  static readonly string Pack=AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
  Label status;
  [STAThread] public static int Main(string[] args) {
   Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
   if(args.Length==2 && args[0]=="--self-test")return SelfTest(args[1]);
   Application.ThreadException+=delegate(object s,System.Threading.ThreadExceptionEventArgs e){MessageBox.Show(e.Exception.Message,"LVW操作未完成");};
   Application.Run(new Launcher());return 0;
  }
  public Launcher() {
   Text="LVW · 图文与视频统一工作台";ClientSize=new Size(570,390);MinimumSize=new Size(586,429);StartPosition=FormStartPosition.CenterScreen;
   Font=new Font("Microsoft YaHei UI",10);BackColor=Color.FromArgb(243,246,250);
   try{Icon=Icon.ExtractAssociatedIcon(Application.ExecutablePath);}catch{}
   Controls.Add(new Label{Text="图文与视频，同一个工作台",Left=28,Top=28,Width=510,Height=40,Font=new Font(Font.FontFamily,20,FontStyle.Bold),ForeColor=Color.FromArgb(23,60,100)});
   Controls.Add(new Label{Text="上传、分析、查看结果、编辑导出，无需操作节点。",Left=30,Top=82,Width=510,Height=28});
   AddButton("打开图片／视频统一工作台",126,delegate{StartWorkbench();});
   AddButton("查看验收报告与验证视频",184,delegate{Open(Path.Combine(Pack,"验收报告与盲测视频.html"));});
   AddButton("打开使用与验收指南",242,delegate{Open(Path.Combine(Pack,"人工验收指南.html"));});
   status=new Label{Text="启动后，在页面点击“启动模型服务”。\n保留服务窗口；结束前先导出，再按 Ctrl+C 停止。\n关闭本窗口不会强制结束任何服务。",Left=30,Top=308,Width=510,Height=74,ForeColor=Color.FromArgb(56,76,97)};Controls.Add(status);
  }
  void AddButton(string text,int top,EventHandler click) {
   var b=new Button{Text=text,Left=30,Top=top,Width=508,Height=42,BackColor=Color.White,FlatStyle=FlatStyle.Flat};b.FlatAppearance.BorderColor=Color.FromArgb(197,208,224);b.Click+=click;Controls.Add(b);
  }
  static void Open(string file){if(!File.Exists(file))throw new FileNotFoundException("找不到项目文件",file);Process.Start(new ProcessStartInfo(file){UseShellExecute=true});}
  void StartWorkbench(){Open(Path.Combine(Pack,"START_LVW.cmd"));status.Text="正在启动统一工作台，请等待浏览器打开。\n图片与视频均在同一个页面选择。\n模型未运行时，在页面点击“启动模型服务”。";}
  static int SelfTest(string receipt){
   try{
    if(!File.Exists(Path.Combine(Pack,"START_LVW.cmd")))throw new Exception("Missing launcher command");
    if(!File.Exists(Path.Combine(Pack,@"lvw\frontend\dist\index.html")))throw new Exception("Missing built frontend");
    using(var form=new Launcher())using(var bitmap=new Bitmap(form.ClientSize.Width,form.ClientSize.Height)){
     using(var canvas=Graphics.FromImage(bitmap))canvas.Clear(form.BackColor);
     foreach(Control c in form.Controls){c.CreateControl();using(var child=new Bitmap(c.Width,c.Height)){c.DrawToBitmap(child,new Rectangle(0,0,c.Width,c.Height));using(var canvas=Graphics.FromImage(bitmap))canvas.DrawImageUnscaled(child,c.Location);}}
     bitmap.Save(Path.Combine(Path.GetDirectoryName(receipt),"launcher-preview.png"));
    }
    File.WriteAllText(receipt,"{\"decision\":\"UNIFIED_LAUNCHER_OFFSCREEN_VERIFIED_NOT_SERVICE_ACCEPTANCE\",\"comfy_dependency\":false,\"visible_windows\":0,\"services_started\":0}",new UTF8Encoding(false));return 0;
   }catch(Exception e){File.WriteAllText(receipt,"FAIL: "+e,new UTF8Encoding(false));return 1;}
  }
 }
}
