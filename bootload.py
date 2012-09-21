#!/usr/bin/env python

import serial

bootloader_error_codes = {
  '0' : "OK",
  '1' : "Intel HEX Invalid",
  '2' : "Bad Checksum",
  '3' : "Bad Address",
  '4' : "Bad Record Type",
  '5' : "Record Too Long"
}

def download_code(ihx_file, serial_port):
  for line in ihx_file.readlines():
    record_type = int(line[7:9], 16)
    if (record_type == 0x00):
      print "Writing", line[:-1],
      serial_port.write(line)
      rc = serial_port.read()
      print " RC =", rc,
      if rc in bootloader_error_codes:
        print "(%s)" % bootloader_error_codes[rc]
      else:
        print "(Unknown Error)"
      if (rc != '0'):
        print "Error downloading code!"
        return False
    else:
      print "Skipping non data record: '%s'" % line[:-1]
  return True

def verify_code(ihx_file, serial_port):
  for line in ihx_file.readlines():
    record_type = int(line[7:9], 16)
    if (record_type == 0x00):
      length= int(line[1:3], 16)
      start_addr= int(line[3:7], 16)
      data= line[9:9+(length*2)]
      # we can only read 16 byte chunks on 16 byte boundries
      block_start= (start_addr / 16) * 16
      offset= (start_addr - block_start)
      block_length= (((length + offset) / 16) + 1) * 16
      print "\rVerifying %04d bytes at address: %04X" % (length, start_addr),
      do_flash_read(serial_port, block_start, block_length)
      verify_data= ''
      for read_data in serial_port:
        read_data= read_data.strip()
        if (not data or read_data == ":00000001FF"):
            break
        # strip header and checksum
        verify_data += read_data[9:-2]
      if (data == verify_data[offset*2:(offset*2)+(length*2)]):
        print '(OK)',
      else:
        print 'Failed! Expected:', data, 'Got:', verify_data[offset*2:(offset*2)+(length*2)]
        exit(1)
      sys.stdout.flush()
    else:
      print "Skipping non data record: '%s'" % line[:-1]
  return True

def run_user_code(serial_port):
  # User code is entered on intel HEX EOF record
  serial_port.write(":00000001FF\n")
  return True
  
def reset_bootloader(serial_port):
  serial_port.write(":00000022DE\n")
  rc = serial_port.read()
  print "RC =", rc,
  if rc in bootloader_error_codes:
    print "(%s)" % bootloader_error_codes[rc]
  else:
    print "(Unknown Error)"
  if (rc != '0'):
    print "Error resetting bootloader!"
    return False
  return True

def erase_all_user(serial_port):
  serial_port.write(":00000023DD\n")
  rc = serial_port.read()
  print "RC =", rc,
  if rc in bootloader_error_codes:
    print "(%s)" % bootloader_error_codes[rc]
  else:
    print "(Unknown Error)"
  if (rc != '0'):
    print "Error erasing all user flash!"
    return False
  return True
  
def erase_user_page(serial_port, page):
  chksum = (0xDB + 0x100 - page) & 0xFF
  serial_port.write(":01000024%02X%02X\n" % (page, chksum))
  rc = serial_port.read()
  print "RC =", rc,
  if rc in bootloader_error_codes:
    print "(%s)" % bootloader_error_codes[rc]
  else:
    print "(Unknown Error)"
  if (rc != '0'):
    print "Error erasing user flash page!"
    return False
  return True

def do_flash_read(serial_port, start_addr, length):
  chksum = (0xD9 + 
            (0x100 - (start_addr & 0xFF)) +
            (0x100 - ((start_addr>>8) & 0xFF)) +
            (0x100 - (length & 0xFF)) +
            (0x100 - ((length>>8) & 0xFF))
           ) & 0xFF
  serial_port.write(":02%04X25%04X%02X\n" % (start_addr, length, chksum))


def flash_read(serial_port, start_addr, length):
  do_flash_read(serial_port, start_addr, length)
  for line in serial_port:
    if not line == "\n":
        print line,
        if (line == ":00000001FF\n"):
          break

def print_usage():
  import sys
  print """
CC Bootloader Download Utility

Usage:  ./bootload.py serial_port command

Commands:

  download <hex_file>

    Download hex_file to the device.
    
  run

    Run the user code.
    
  reset

    The bootloader will not erase pages that have previously been written to
    before writing new data to that page. This allows for random access writes
    but prevents you from overwriting downloaded code unless the device is
    power cycled. This command will reset the bootloader's record of what
    pages have been written to, allowing you to overwrite without power 
    cycling.
    
  erase_all

    Erases the entire user flash area.
    
  erage <n>

    Erases page n of the flash memory (organised into 1024 byte pages). The
    bootloader occupies the first few pages and the rest are reserved for user
    code. Attempting to erase a bootloader page will have no effect. To
    determine which page the user code starts on please check the
    USER_CODE_BASE setting in main.h.
    
  read <start_addr> <len>

    Reads len bytes from flash memory starting from start_addr. start_addr and
    len should be specified in hexadecimal (e.g. 0x1234) and len must be a multiple
    of 16. Output is compatible with download and verify commands.

  verify <hex_file>

    Verify hex_file matches device flash memory.
  """

if __name__ == '__main__':
  import sys
  if (len(sys.argv) < 3):
    print_usage()
    sys.exit(1)
    
  serial_port_name = sys.argv[1]
  command = sys.argv[2]
  options = sys.argv[3:]
  serial_port = serial.Serial(serial_port_name, timeout=1)
  
  try:
    if (command == 'download' or command == 'verify'):
      if (len(options) < 1):
        print_usage()
      else:
        ihx_filename = options[0]
        ihx_file = open(ihx_filename, 'r')
        if (command == 'download'):
          download_code(ihx_file, serial_port)
        else:
          verify_code(ihx_file, serial_port)
        
    elif (command == 'run'):
      run_user_code(serial_port)
      
    elif (command == 'reset'):
      reset_bootloader(serial_port)
      
    elif (command == 'erase_all'):
      erase_all_user(serial_port)
      
    elif (command == 'erase'):
      if (len(options) < 1):
        print_usage()
      else:
        erase_user_page(serial_port, int(options[0]))
        
    elif (command == 'read'):
      if (len(options) < 2):
        print_usage()
      else:
        flash_read(serial_port, int(options[0], 16), int(options[1], 16))
        
        
    else:
      print_usage()
  finally:
    serial_port.close()



