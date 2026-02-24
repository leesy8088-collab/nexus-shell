Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\³»Æú´õ\SOS\nexus_shell"
WshShell.Run "python main.py > nexus.log 2>&1", 0, False