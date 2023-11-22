import pyvisa as visa
import pylab as pl
import csv

def main():
    _rm = visa.ResourceManager()
    sds = _rm.open_resource("USB0::0xF4ED::0xEE3A::SDS1ECDD2R9854::INSTR")
    sds.write("chdr off")
    print("Acquire way:", sds.query("acquire_way?").replace('\n', ''))
    trmd = sds.query("trig_mode?").replace('\n', '')
    print("Trigger mode: ", trmd)
    #### set memory size (14k, 140k, 1.4M, 14M) ####
    msiz = "140k"
    if msiz.upper() not in sds.query("memory_size?").replace('\n', ''):
        if "STOP" in trmd:
            sds.write("trmd norm")
        sds.write("msiz " + msiz)
        sds.write("trmd " + trmd)
    print("Memory size:", sds.query("memory_size?").replace('\n', ''))

    vdiv = float(sds.query("c1:vdiv?"))
    ofst = float(sds.query("c1:ofst?"))
    tdiv = float(sds.query("tdiv?"))
    sara = sds.query("sara?")
    print("vdiv: ", vdiv, " ofst: ", ofst, " tdiv: ", tdiv)
    sara_unit = {'G': 1E9, 'M': 1E6, 'k': 1E3}

    for unit in sara_unit.keys():
        if sara.find(unit) != -1:
            sara = sara.split(unit)
            sara = float(sara[0])*sara_unit[unit]
            break
    sara = float(sara)

    print("Sample Rate: ", f'{sara:,}')
    sds.timeout = 30000  # default value is 2000(2s)
    sds.chunk_size = 20*1024*1024  # default value is 20*1024(20k bytes)
    sds.write("c1:wf? dat2")
    #recv = list(sds.read_raw())[16:] ### skip header, ex. DAT2,#9003500000
    #recv.pop()
    #recv.pop()
    recv = list(sds.read_raw())
    volt_len = 0
    if recv[len(recv)-2] == 10 and recv[len(recv)-1] == 10:
        print("Received data OK")
        volt_len = int(''.join(str(digit-48) for digit in recv[9:16]))
        print("Volt len: ", f'{volt_len:,}')
    else:
        print("Received data truncated")
        exit()
    volt_value = []
    for data in recv[16:len(recv)-2]: ### skip header, trunkate end "aa" ###
        if data > 127:
            data = data - 256
        else:
            pass
        volt_value.append(data)
    print("Volt values: ", f'{len(volt_value):,}')
    if len(volt_value) != volt_len:
        print("Wrong data size")
        exit()
    if len(volt_value) == 0:
        print("No data")
        exit()
    
    ### values below thres are low and above high ###
    v_max = max(volt_value[100:len(volt_value)-100])
    v_min = min(volt_value[100:len(volt_value)-100])
    tresh = (v_max - v_min) / 2
    tresh_offset = 2 ### avoid false detection ###
    print ("Max: %.2fV, Min: %.2fV, Treshold: %d, %.2fV" % (v_max/25*vdiv-ofst, v_min/25*vdiv-ofst, tresh, tresh/25*vdiv-ofst))
    high = False
    time_table = []
    time_high = []
    time_volt = []
    time_width = []
    
    ### create table with time stamps for level changes ###
    for idx in range(0, len(volt_value), 1):
        v = volt_value[idx]
        if v > tresh + tresh_offset and not high: ### change from low to high ###
            time_table.append(-(tdiv*14/2)+idx*(1/sara))
            time_volt.append(v/25*vdiv-ofst)
            time_high.append(True)
            high = True
        elif v < tresh - tresh_offset and high: ### change from high to low ###
            time_table.append(-(tdiv*14/2)+idx*(1/sara))
            time_volt.append(v/25*vdiv-ofst)
            time_high.append(False)
            high = False

    ### calculate pulse width high and low ###
    for idx in range(1, len(time_table)):
        time_width.append(time_table[idx] - time_table[idx-1])
    time_width.append(-(tdiv*14/2)+len(volt_value)*(1/sara) - time_table[idx])

    with open('pulse_list.csv', 'w', newline='') as csvfile:
        fieldnames = ['time', 'width', 'cnt', 'level', 'volt']
        pulsefile = csv.writer(csvfile, delimiter=';')
        pulsefile.writerow(fieldnames)
        
        hdr = ["{0: >9}".format("Time"),
              "{0: >8}".format("Width"),
              "{0: >3}".format("Nr"),
              "{0: <5}".format("HIGH"),
              "{0: >6}".format("Volt")]
        #print(*hdr)
        for idx in range(0, len(time_table)):
            row = ["{:6.2f}".format(time_table[idx] * 1000),
                  "{:5.0f}".format(time_width[idx] * 1000 * 1000),
                  "{:3.0f}".format(idx / 2 + 0.5 + 0.5 * int(time_high[idx] == True)),
                  "{0: <5}".format(str(time_high[idx])),
                  "{:6.2f}".format(time_volt[idx])]
            #print(row[0], "ms", row[1], "us", *row[2:5])
            pulsefile.writerow(row)

    ### create plot ###
    time_value = []
    for idx in range(0, len(volt_value)):
        volt_value[idx] = volt_value[idx]/25*vdiv-ofst
        time_data = -(tdiv*14/2)+idx*(1/sara)
        time_value.append(time_data)

    pl.figure(figsize=(7, 5))
    pl.plot(time_value, volt_value, markersize=2, label=u"Y-T")
    pl.legend()
    pl.grid()
    #pl.show()

if __name__ == '__main__':
    main()
