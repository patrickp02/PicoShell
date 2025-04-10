import os
import utils
import network
import platform
import machine
import gc
###
bold = "\033[1m"
green = "\033[32m"
blue = "\033[34m"
reset = "\033[0m"
its = 0 
sys_info = os.uname()
while True:
    try:  
        command = input(f"{bold}{green}Pico@{sys_info.sysname}{reset}:{blue}{os.getcwd()}{reset}$ ")
        if command == 'wifi':
            utils.getWifi()
            
        
        elif command == 'help' or command == 'h':
            try:
                with open("/docs/help.txt") as f:
                    print(f.read())
            except Exception as e:
                print("Help file does not exist.", e)

        elif command == 'ls':
            utils.ls()
        
        elif command == 'exit':
            break

        elif command.startswith("run "):
            script_name = command[4:].strip()  
            utils.run(script_name)
            
        elif command.startswith("cd "):
            dir = command[3:].strip()
            utils.cd(dir)
            
        elif command == 'ifconfig':
            utils.if_config()
        
        elif command.startswith("ping "):
            host = command[5:].strip()
            utils.ping(host)
        
        elif command.startswith("curl "):
            url = command[5:].strip()
            utils.curl(url)
            
        elif command.startswith('telnet '):
            tel = command[7:].strip()
            utils.telnet_launch(tel)
            
        elif command.startswith('mkdir '):
            dir = command[6:].strip()
            utils.mkdir(dir)
            
        elif command.startswith('rmdir '):
            dir = command[6:].strip()
            utils.rmdir(dir)
        
        elif command.startswith('rm '):
            file = command[3:].strip()
            utils.rm(file)
        
        elif command == 'sysinfo':
            utils.sysinfo()
        
        elif command == 'dspace':
            utils.get_storage()
        
        elif command == 'about':
            print(platform.platform())
        
        elif command == 'clock':
            print("CPU Clock:", machine.freq() // 1_000_000, "MHz")
            
        elif command.startswith('setclock '):
            clock = int(command[9:].strip())
            utils.overclock(clock)
            
        elif command == 'scan':
            utils.scan()
            
        elif command.startswith('clone '):
            try:   
                args = command[6:].strip().split()
                url = args[0]
                filename = args[1] if len(args) > 1 else url.rsplit('/', 1)[-1]
                utils.download_file(url, filename)
                print(f"Downloading {filename} from {url}")
            except Exception as e:
                print("Download failed:", e)
        
        elif command.startswith("pmap "):
            parts = command.split()
            ip = parts[1]
            start = int(parts[2]) if len(parts) > 2 else 1
            end = int(parts[3]) if len(parts) > 3 else 1024
            utils.scan_ports(ip, start, end)

        
        elif command == 'clear':
            print('\033c', end='')
        
        elif command.startswith('blink'):
            utils.blink()
        
        elif command == 'reboot':
            print("Rebooting.")
            machine.reset()
        
        elif command == 'reset':
            print("Reseting")
            machine.soft_reset()
            
        elif command.startswith('read '):
            fName = command[4:].strip()
            utils.read(fName)
        
        elif command == 'ram':
            print("Free:", gc.mem_free()/1024, "kilobytes")
            print("Used:", gc.mem_alloc()/1024, "kilobytes")
            print("Total:", (gc.mem_alloc() + gc.mem_free())/1024, "kilobytes")
            
        elif command == 'pwd':
            print(os.getcwd())

        elif command == 'temp':
            print(f"CPU Temp: {utils.read_temp():.2f} °C")

                                
        its += 1

        lif its % 5 == 0 and its != 0: 
            gc.collect()

        #else:
            #print("Unknown Command")
    except Exception as e:
        print("CLI ERROR: ",e)
    
    except KeyboardInterrupt:
        print()
        continue
        
            
            
            
         
                
                
                              
        
