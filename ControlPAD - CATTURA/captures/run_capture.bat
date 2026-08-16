@echo off
"C:\Program Files\USBPcap\USBPcapCMD.exe" -d \\.\USBPcap2 -A --inject-descriptors -o "%~1" > "C:\Users\nsdav\Desktop\ControlPAD - CATTURA\captures\test_log.txt" 2>&1
