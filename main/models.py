import datetime as dt
import pytz
import os
import itertools
from operator import add
from decimal import *

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum, F, Value
import pandas
import numpy as np

from .utils import *


def getFlightAt(flights, time):
    f = list(filter(lambda x: time >= x.time_off
                              and time <= x.time_on, flights))
    if len(f) == 0:
        return None
    else:
        return f[0]


# abstact model for data of all device
# child class must implement save_file, get_serial_num, integrate_dose
# and have attr metadata
class AData(models.Model):
    file_fk = models.ForeignKey('DataFile', on_delete=models.CASCADE)
    flight_fk =  models.ForeignKey('Flight', on_delete=models.SET_NULL,
                                   null=True)
    time = models.DateTimeField()

    # example of metadata attr
    metadata = {
            # name of device
            "name" : "data",
            # extension of file use in js regex for choose device type
            "fileExt" : ".my_ext",
            # list of attr to display
            "columns" : [
                    # name use for display, attr use for getattr()
                    {"name" : "time utc", "attr" : "time"}
                ]
            }
    
    # parse file or filename and return serial_num
    def get_serial_num(file_):
        raise NotImplemented

    # parse file and save data in db, can throw
    def save_file(datafile, file_):
        raise NotImplemented

    # integrate dose of data list return IntegratedDose or None
    def integrate_dose(data):
        raise NotImplemented

    # data = list of AData, time = fligth.time_off
    # return {'time' : ['0000-01-01 00:00:34', ...],
    #       'bas' : [...], 'haut' : .[..], 'total' : [...]}
    def dose_rate(data, time):
        raise NotImplemented

    def __str__(self):
        return (self.time.strftime("%d/%m/%Y %H:%M:%S"))

    class Meta:
        abstract = True


class DataEPDN2(AData):
    gamma = models.IntegerField(default=0)
    neutron = models.IntegerField(default=0)
    
    metadata = {
        "name" : "EPDN2",
        "fileExt" : "^\d{7}.txt",
        "columns" : [
            {"name" : "gamma", "attr" : "gamma"},
            {"name" : "neutron", "attr" : "neutron"}
        ]
    }

    def get_serial_num(file_):
        return os.path.splitext(file_.name)[0]

    def save_file(datafile, file_):
        data = []
        df = pandas.read_csv(file_, skipinitialspace=True, encoding="utf-16le")
        date = dt.datetime.strptime(df["DateHeure"][len(df.index) - 1],
                                    "%d/%m/%Y %H:%M:%S")
        utc_off = pytz.timezone("Europe/Paris").localize(date).utcoffset()
        flights = datafile.flight_file_fk.flight_set.all()
        for idx in range(len(df.index) - 2, -1, -1):
            date = dt.datetime.strptime(df["DateHeure"][idx],
                                        "%d/%m/%Y %H:%M:%S")
            time = (date - utc_off).replace(tzinfo=pytz.utc)
            gamma = df["HpG uSv"][idx] - df["HpG uSv"][idx + 1]
            neutron = df["HpN uSv"][idx] - df["HpN uSv"][idx + 1]
            if gamma > 0 or neutron > 0:
                data.append(DataEPDN2(
                    file_fk=datafile, flight_fk=getFlightAt(flights, time),
                    time=time, gamma=gamma, neutron=neutron))
        DataEPDN2.objects.bulk_create(data)   

    def integrate_dose(data):
        bLET = 0
        hLET = 0
        for d in data:
            bLET += d.gamma
            hLET += d.neutron
        return IntegratedDose(dose=(bLET + hLET), bas_LET=bLET, haut_LET=hLET)

    def dose_rate(data, time):
        prev_bas = time
        prev_haut = time
        rate = {'time' : [], 'bas' : [], 'haut' : [], 'total' : []}
        xb = []
        yb = []
        xh = []
        yh = []
        x = []
        for d in data:
            bas = None
            haut = None
            t = d.time - time
            if d.gamma != 0:

                if prev_bas != time:
                    time_diff = (d.time - prev_bas).total_seconds()
                    yb.append(d.gamma / (time_diff / 3600))
                    xb.append(t.total_seconds())
                prev_bas = d.time
            if d.neutron != 0:
                if prev_haut != time:
                    time_diff = (d.time - prev_haut).total_seconds()
                    yh.append(d.neutron / (time_diff / 3600))
                    xh.append(t.total_seconds())
                prev_haut = d.time
            x.append(t.total_seconds())
            rate['time'].append('0000-01-01 ' + str(t))
        rate['bas'] = np.interp(x, xb, yb).tolist()
        rate['haut'] = np.interp(x, xh, yh).tolist()
        rate['total'] = list(map(add, rate['bas'], rate['haut']))
        return rate
       

class DataLiulin(AData):
    dose = models.DecimalField(max_digits=14, decimal_places=7)
    flux = models.DecimalField(max_digits=14, decimal_places=7)
    spectrum = models.TextField(default=0)
    
    metadata = {
        "name" : "Liulin",
        "fileExt" : ".s\d*",
        "columns" : [
            {"name" : "dose", "attr" : "dose"},
            {"name" : "flux", "attr" : "flux"}
        ]
    }

    def get_serial_num(file_):
        header = file_.readline().decode('ascii').split(' ')
        file_.seek(0, 0)
        return header[0]

    def save_file(datafile, file_):
        data = []
        df = pandas.read_csv(file_, delim_whitespace=True, skiprows=2, header=None)
        date = dt.datetime.strptime(df[0][1] + " " + df[1][1],
                                    "%d/%m/%y %H:%M:%S")
        utc_off = pytz.timezone("Europe/Paris").localize(date).utcoffset()
        flights = datafile.flight_file_fk.flight_set.all()
        file_.seek(0, 0)
        file_.readline()
        file_.readline()
        for idx in range(0, len(df.index) - 1, 2):
            spec = file_.readline().decode('ascii').strip().replace(" ", ";")
            file_.readline()
            date = dt.datetime.strptime(df[0][idx + 1] + " " + df[1][idx + 1],
                                        "%d/%m/%y %H:%M:%S")
            time = (date - utc_off).replace(tzinfo=pytz.utc)
            data.append(DataLiulin(
                file_fk=datafile, flight_fk=getFlightAt(flights, time),
                time=time, dose=df[4][idx + 1],
                flux=df[7][idx + 1], spectrum=spec
                ))
        DataLiulin.objects.bulk_create(data)

    def integrate_dose(data):
        bLET = 0
        hLET = 0
        tot = 0
        if len(data) < 2:
            return None
        expo = data[1].time - data[0].time
        for d in data:
            channels = d.spectrum.split(';')
            tot += float(d.dose) * (expo.total_seconds() / 3600)
            for i in range(1, 256):
                if i <= 12:
                    bLET += int(channels[i]) * (40.7 + 81.4 * (i - 1))
                else:
                    hLET += int(channels[i]) * (40.7 + 81.4 * (i - 1))
        tLET = bLET + hLET
        return IntegratedDose(dose=tot, bas_LET=(bLET / tLET * tot),
                              haut_LET=(hLET / tLET * tot))
    
    def dose_rate(data, time):
        rate = {'time' : [], 'total' : [], 'bas' : [], 'haut' : []}
        for d in data:
            channels = d.spectrum.split(';')
            bLET = 0
            hLET = 0
            for i in range(1, 256):
                if i <= 12:
                    bLET += int(channels[i]) * (40.7 + 81.4 * (i - 1))
                else:
                    hLET += int(channels[i]) * (40.7 + 81.4 * (i - 1))
            tLET = bLET + hLET
            rate['time'].append('0000-01-01 ' + str(d.time - time))
            rate['total'].append(d.dose)
            rate['bas'].append(float(d.dose) * (bLET / tLET))
            rate['haut'].append(float(d.dose) * (hLET / tLET))
        return rate
 




class DataHawk(AData):
    volt = models.DecimalField(max_digits=14, decimal_places=7)
    current = models.DecimalField(max_digits=14, decimal_places=7)
    temp = models.DecimalField(max_digits=14, decimal_places=7)
    qfactor = models.DecimalField(max_digits=14, decimal_places=7)
    gamma_dose = models.DecimalField(max_digits=14, decimal_places=7)
    dose_equ = models.DecimalField(max_digits=14, decimal_places=7)
    bas_LET = models.DecimalField(max_digits=14, decimal_places=7)
    haut_LET = models.DecimalField(max_digits=14, decimal_places=7)

    metadata = {
        "name" : "Hawk",
        "fileExt" : ".txt",
        "columns" : [
            {"name" : "volt", "attr" : "volt"},
            {"name" : "current", "attr" : "current"},
            {"name" : "temp", "attr" : "temp"},
            {"name" : "Q factor", "attr" : "qfactor"},
            {"name" : "gamma dose", "attr" : "gamma_dose"},
            {"name" : "dose equ", "attr" : "dose_equ"},
            {"name" : "bas LET", "attr" : "bas_LET"},
            {"name" : "haut LET", "attr" : "haut_LET"},
        ]
    }

    def get_serial_num(file_):
        for i in range(0, 4):
            s = file_.readline()
        num = s.decode('ascii').split(":")[-1].strip()[4:-4]
        file_.seek(0, 0)
        return num

    def save_file(datafile, file_):
        while 1:
            line = file_.readline()
            if chr(line[0]) == ',':
                break
        df = pandas.read_csv(file_, header=None, skiprows=1,
                             skipinitialspace=True)
        for col in df.columns:
            if hasattr(df[col], "str"):
                df[col] = df[col].str.strip()
        data = []
        date = dt.datetime.strptime(df[1][0] + " " + df[2][0],
                                    "%H:%M:%S %d%b%y")
        flights = datafile.flight_file_fk.flight_set.all()
        utc_off = pytz.timezone("Europe/Paris").localize(date).utcoffset()
        coef = Coefficient.objects.filter(start__lte=date,
                                          device_fk=datafile.device_fk).last()
        for i in range(0, len(df.index) - 1):
            params = {}
            time = dt.datetime.strptime(df[1][i] + " " + df[2][i],
                                              "%H:%M:%S %d%b%y")
            params["time"] = (time - utc_off).replace(tzinfo=pytz.utc)
            params["volt"] = unitConv(df[4][i].item(), df[5][i], "V")
            params["current"] = unitConv(df[6][i], df[7][i], "µA")
            params["temp"] = unitConv(df[8][i].item(), df[9][i], "C")
            params["qfactor"] = df[29][i]
            params["gamma_dose"] = unitConv(df[35][i], df[36][i], "µG") 
            params["dose_equ"] = unitConv(df[37][i], df[38][i], "µS")
            params["bas_LET"] = params["gamma_dose"] * float(coef.bas_LET)
            params["haut_LET"] = (params["dose_equ"] - params["gamma_dose"]) \
                * float(coef.haut_LET)
            params["flight_fk"] = getFlightAt(flights, params["time"])
            data.append(DataHawk(file_fk=datafile, **params))
        DataHawk.objects.bulk_create(data)

    def integrate_dose(data):
        bLET = 0
        hLET = 0
        for d in data:
            bLET += d.bas_LET
            hLET += d.haut_LET
        return IntegratedDose(dose=(bLET + hLET), bas_LET=bLET, haut_LET=hLET)
    
    def dose_rate(data, time):
        prev_time = time
        rate = {'time' : [], 'bas' : [], 'haut' : [], 'total' : []}
        for d in data:
            time_diff = (d.time - prev_time).total_seconds()
            rate['time'].append('0000-01-01 ' + str(d.time - time))
            if time_diff == 0:
                bas = 0
                haut = 0
            else:
                bas = float(d.bas_LET) / (time_diff / 3600)
                haut = float(d.haut_LET) / (time_diff / 3600)
            rate['bas'].append(bas)
            rate['haut'].append(haut)
            rate['total'].append(bas + haut)
            prev_time = d.time
        return rate
 


# Add device models before


# dict for AData subclasses ex : {"DataEPDN2" : DataEPDN2, ...}
deviceDict = {cl.__name__ : cl for cl in AData.__subclasses__()}
# list of AData subclasses ex [DataEPDN2, ...]
deviceList = AData.__subclasses__()
# tuple of tuple for AData subclasses ex : (("DataEPDN2", "EPDN2"), ...)
deviceChoises = [(cl.__name__, cl.metadata["name"]) for cl in AData.__subclasses__()]


class Device(models.Model):
    dtype = models.CharField(max_length=255, choices=tuple(deviceChoises))
    version_fk = models.ForeignKey('DeviceVersion', null=True, blank=True,
                                   on_delete=models.SET_NULL)
    serial_num = models.CharField(max_length = 256)

    def __str__(self):
        vers = ""
        if self.version_fk is not None:
            vers = self.version_fk.version + "-"
        return (deviceDict[self.dtype].metadata["name"] + "-" 
                + vers + self.serial_num)

class DataFile(models.Model):
    flight_file_fk = models.ForeignKey('FlightFile', on_delete=models.CASCADE)
    filename = models.CharField(max_length = 255)
    upload_date = models.DateTimeField('date uploaded', auto_now_add=True)
    device_fk = models.ForeignKey('Device', on_delete=models.CASCADE)

    def __str__(self):
        return (self.filename)


class IntegratedDose(models.Model):
    flight_fk = models.ForeignKey('Flight', on_delete=models.CASCADE)
    datafile_fk = models.ForeignKey('DataFile', on_delete=models.CASCADE)
    dose = models.DecimalField(max_digits=14, decimal_places=7, null=True)
    bas_LET = models.DecimalField(max_digits=14, decimal_places=7, null=True)
    haut_LET = models.DecimalField(max_digits=14, decimal_places=7, null=True)


class FlightFile(models.Model):
    filename = models.CharField(max_length=255)
    user_fk = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    upload_date = models.DateTimeField('date uploaded', auto_now_add=True)
    matricule = models.CharField(max_length=32)
    model = models.CharField(max_length=32)

    def __str__(self):
        return (self.filename)


class Flight(models.Model):
    file_fk = models.ForeignKey(FlightFile, on_delete=models.CASCADE)
    num = models.CharField(max_length=32)
    airport_from = models.CharField(max_length=255)
    airport_to = models.CharField(max_length=255)
    time_dep = models.DateTimeField()
    time_arr = models.DateTimeField()
    time_out = models.DateTimeField()
    time_off = models.DateTimeField()
    time_on = models.DateTimeField()
    time_in = models.DateTimeField()

    def __str__(self):
        return (self.num)


class DeviceVersion(models.Model):
    dtype = models.CharField(max_length=255, choices=tuple(deviceChoises))
    version = models.CharField(max_length=255)

    def __str__(self):
        return (deviceDict[self.dtype].metadata["name"] + "-" + self.version)


class Coefficient(models.Model):
    device_fk = models.ForeignKey(Device, on_delete=models.CASCADE)
    start = models.DateField()
    bas_LET = models.DecimalField(max_digits=14, decimal_places=7)
    haut_LET = models.DecimalField(max_digits=14, decimal_places=7)
    
    def __str__(self):
        return str(self.bas_LET) + ", " + str(self.haut_LET)
        
    class Meta:
        ordering = ['start']
 


class CustomPermission(models.Model):

    class Meta:
        managed = False
        permissions = (
                ("add", "Add data"),
                ("upload", "Upload data"),
                ("view", "View data"),
            )
