import datetime as dt
import pytz
import io

from django.contrib.auth.decorators import permission_required
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Min, Sum, Avg, F, Value, Q, Case, When
from django.db.models.functions import Concat
from django.http import HttpResponse, JsonResponse
import dateparser
import pandas
import numpy

from .models import *
from .utils import *


def home(request):
    return (render(request, "home.html", {}))

# login page
def login_view(request):
    if request.method == "POST":
        user = authenticate(request, username=request.POST["username"],
            password=request.POST["password"])
        if user is not None:
            login(request, user)
            return (redirect(request.GET.get("next", "home")))
        else:
            return (render(
                request, "login.html", 
                {'errors' : ["Bad username or password."]}))
    else:
        return (render(request, "login.html", {}))


# logout page
def logout_view(request):
    logout(request)
    return (render(request, "logout.html", {}))


def add_date_time(date, time_str, tformat):
    time = dt.datetime.strptime(time_str, tformat)
    return date_inc(date, time).replace(tzinfo=pytz.utc)


# parse and save flightflie in db return flightfile or None on error
def save_flight_file(file_, year, user):
    try:
        # Parse file header (matricule, model)
        df_h = pandas.read_csv(
            file_, skipinitialspace=True, sep=';',
            skiprows=3, nrows=1, header=None)
        flight_file = FlightFile(
            filename=getattr(file_, "name", "input"), 
            matricule=df_h[0][0].split(' ')[-1],
            model=df_h[1][0].split(' ')[-1],
            user_fk=user)
        flight_file.save()
    except Exception as e:
        print("Error", type(e).__name__, e)
        return None
    try:
        # Parse file body
        file_.seek(0, 0)
        df = pandas.read_csv(file_, skipinitialspace=True, sep=';', skiprows=5,
                            dtype={"N volCause IRG" : object})
        flights = []
        old_date = None
        for idx in range(0, len(df.index)):
            if (isnotnan(df["OFF"][idx]) and isnotnan(df["ON"])
                    and df["ON"][idx][0] == 'A'):
                dstr = df["Date TdL"][idx] + " " + df["Dep..1"][idx] \
                    + " " + year
                date = dateparser.parse(
                    dstr, settings={"PREFER_DATES_FROM" : "past",
                                    "DATE_ORDER" : "DMY"})
                if (year != "" and old_date != None and old_date > date):
                    date.replace(year=date.year + 1)
                date_arr = add_date_time(date, df["Arr..1"][idx], "%H:%M:%S")
                date_out = add_date_time(date, df["OUT"][idx][-5::], "%H:%M")
                date_off = add_date_time(date, df["OFF"][idx][-5::], "%H:%M")
                date_on = add_date_time(date, df["ON"][idx][-5::], "%H:%M")
                date_in = add_date_time(date, df["IN"][idx][-5::], "%H:%M")
                flights.append(Flight(
                    file_fk=flight_file,
                    num=" ".join(df["N volCause IRG"][idx].split()),
                    airport_from=" ".join(df["Dep."][idx].split()),
                    airport_to=" ".join(df["Arr."][idx].split()),
                    time_dep=date.replace(tzinfo = pytz.utc),
                    time_arr=date_arr, time_out=date_out, time_off=date_off,
                    time_on=date_on, time_in=date_in
                    ))
        Flight.objects.bulk_create(flights)
        return flight_file
    except Exception as e:
        print("Error", type(e).__name__, e)
        flight_file.delete()
        return None


# parse and save dataflie in db return datafile or None on error
def save_data_file(file_, dtype, flight_file, version):
        try:
            serial_num = deviceDict[dtype].get_serial_num(file_)
            device = Device.objects.filter(dtype=dtype, version_fk=version,
                                           serial_num=serial_num).get()
            datafile = DataFile(filename=file_.name, flight_file_fk=flight_file,
                                device_fk=device)
            datafile.save()
        except Exception as e:
            print("Error", type(e).__name__, e)
            dev = str(Device(dtype=dtype, version_fk=version, serial_num=serial_num))
            return None, "device " + dev + " does not exist."
        try:
            deviceDict[dtype].save_file(datafile, file_)
            return datafile, None
        except Exception as e:
            print ("Error", type(e).__name__, e)
            datafile.delete()
            return None, "wrong format."


# Compute the integrated dose for all fligths
def idose_flights(datafile, flights):
    data_device = deviceDict[datafile.device_fk.dtype]
    idoses = []
    for flight in flights:
        data = data_device.objects.filter(
            
            flight_fk=flight, file_fk=datafile).all()
        if len(data) != 0:
            idose = data_device.integrate_dose(data)
            if idose is not None:
                idose.datafile_fk = datafile
                idose.flight_fk = flight
                idoses.append(idose)
    return idoses


# Get dict : { dtype : [list of version] }
def get_devices_versions():
    deviceVers = {}
    for dv in DeviceVersion.objects.all():
        deviceVers[dv.dtype] = deviceVers.get(dv.dtype, []) + [dv]
    return deviceVers


# POST : save flightfile and datafiles
# GET : display form
@permission_required('main.upload', 'login')
def upload(request):
    ctxt = {"deviceChoises" : deviceChoises, "deviceList" : deviceList, 
            "deviceVersions" : get_devices_versions()}
    if (request.method == "POST"):
        if (request.POST.get('is_flightfile', False) == False):
            ffile = io.StringIO(request.POST['gen_file'])
        else:
            ffile = request.FILES.getlist('flightfile')[0]
        flightfile = save_flight_file(ffile, request.GET.get("year", ""), request.user)
        if (flightfile == None):
            errors = ["Flight file wrong format"]
            return (render(request, "upload.html", dict(errors=errors, **ctxt)))
        else:
            idoses = []
            for idx, file_ in enumerate(request.FILES.getlist('datafiles')):
                device = request.POST['device' + str(idx)]
                version = request.POST.get('version' + str(idx), None)
                datafile, err = save_data_file(file_, device, flightfile, version)
                if (err != None):
                    flightfile.delete()
                    errors = ["File : " + file_.name + " " + err]
                    return (render(request, "upload.html",
                                   dict(errors=errors, **ctxt)))
                idoses += idose_flights(datafile, flightfile.flight_set.all())
            IntegratedDose.objects.bulk_create(idoses)
            return (redirect('view_flights', flightfile.id))
    else:
        return (render(request, "upload.html", ctxt))


@permission_required('main.upload', 'login')
def del_data(request, id_datafile):
    dfile = get_object_or_404(DataFile, pk=id_datafile)
    fl_id = dfile.flight_file_fk.id
    if (dfile.flight_file_fk.user_fk == request.user or request.user.is_superuser):
        dfile.delete()
        return (redirect('view_flights', id_flightfile=fl_id))
    else:
        return (redirect('login'))

@permission_required('main.upload', 'login')
def del_flights(request, id_flightfile):
    ffile = get_object_or_404(FlightFile, pk=id_flightfile)
    if (ffile.user_fk == request.user or request.user.is_superuser):
        ffile.delete()
        return (redirect('view_flightfiles'))
    else:
        return (redirect('login'))

    

# POST : add new unique device to database
# GET : display form
@permission_required('main.add', 'login')
def add_device(request):
    ctxt = {"deviceChoises" : deviceChoises,
            "deviceVersions" : get_devices_versions()}
    if request.method == "POST":
        dtype = request.POST["device"]
        version = request.POST.get("version", None)
        serial = request.POST["serial"]
        dev, created = Device.objects.get_or_create(
            dtype=dtype,
            version_fk_id=version,
            serial_num=serial)
        if not created:
            return (render(request, "add_device.html",
                           dict(errors=["Already exist"], **ctxt)))
        return (redirect('view_devices'))
    else:
        return (render(request, "add_device.html", ctxt))


# POST : add new unique version to database
# GET : display form
@permission_required('main.add', 'login')
def add_version(request):
    ctxt = {"deviceChoises" : deviceChoises}
    if request.method == "POST":
        dtype = request.POST["device"]
        version = request.POST["version"]
        ver, created = DeviceVersion.objects.get_or_create(
            dtype=dtype,
            version=version)
        if not created:
            return (render(request, "add_version.html",
                           dict(errors=["Already exist"], **ctxt)))
        return (redirect('view_devices'))
 
    else:
        return (render(request, "add_version.html", ctxt))


# POST : add new coeff to database
# GET : display form
@permission_required('main.add', 'login')
def add_coeff(request):
    ctxt = {"devices" : Device.objects.all()}
    if request.method == "POST":
        device = request.POST['device']
        coeff_b = request.POST['bLET']
        coeff_h = request.POST['hLET']
        date = dt.datetime.strptime(request.POST['date'], "%Y-%m-%d")
        Coefficient.objects.create(device_fk_id=device, start=date,
                                   bas_LET=coeff_b, haut_LET=coeff_h)
        return (redirect('view_devices'))
    return (render(request, "add_coeff.html", ctxt))

def search_querry(elem, str_search):
    querry = Q()
    for or_search in str_search.split('/'):
        subquerry = Q()
        for and_search in or_search.split():
            subquerry &= Q(**{elem : and_search})
        querry |= subquerry
    return querry

@permission_required('main.view', 'login')
def rate_(request):
    file_fk = request.GET['file']
    flight_fk = request.GET['flight']
    device = DataFile.objects.get(pk=file_fk).device_fk
    data_dev = deviceDict[device.dtype]
    data = data_dev.objects.filter(file_fk=file_fk, flight_fk=flight_fk).all()
    flight = data[0].flight_fk
    rate = data_dev.dose_rate(data, flight.time_off)
    rate['from'] = flight.airport_from
    rate['to'] = flight.airport_to
    rate['dev'] = str(device)
    return JsonResponse(rate)


@permission_required('main.view', 'login')
def search_(request):
    res = []
    querry = search_querry("num__contains", request.GET["num"]) \
        & search_querry("airport_from__contains", request.GET["dep"]) \
        & search_querry("airport_to__contains", request.GET["arr"])
    if request.GET["min"] != "":
        date = dt.datetime.strptime(request.GET['min'], "%Y-%m-%d")
        querry &= Q(time_off__gte=date)
    if request.GET["max"] != "":
        date = dt.datetime.strptime(request.GET['max'], "%Y-%m-%d")
        date = date.replace(hour=23, minute=59, second=59)
        querry &= Q(time_off__lte=date)
    flights = Flight.objects.filter(querry)
    dev_list = list(map(int, filter(None, request.GET["dev"].split(','))))
    datafiles = DataFile.objects.filter(device_fk_id__in=dev_list).all()
    idoses = IntegratedDose.objects.filter(
        flight_fk__in=flights, datafile_fk__in=datafiles) \
            .order_by('flight_fk__time_off').all()
    for idose in idoses:
        fl = idose.flight_fk
        dev = idose.datafile_fk.device_fk
        elem = {
            "flight_fk" : fl.id, "file_fk" : idose.datafile_fk.id,
            "num" : fl.num, "total" : idose.dose, 
            "haut" : idose.haut_LET, "bas" : idose.bas_LET,
            "from" : fl.airport_from, "to" : fl.airport_to,
            "date" : dt.datetime.strftime(fl.time_off, "%d/%m/%Y"),
            "off" : dt.datetime.strftime(fl.time_off, "%d/%m/%Y %H:%M"),
            "on" : dt.datetime.strftime(fl.time_on, "%d/%m/%Y %H:%M"),
            "device": str(dev),
        }
        res.append(elem)
    df = pandas.DataFrame.from_records(res, columns=[
        'device', 'num', 'from', 'to', 'date', 'off',
        'on', 'bas', 'haut', 'total'])
    forma = request.GET.get('format', 'json')
    if forma == 'json':
        return JsonResponse({'res' : res})
    elif forma == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=dose.csv'
        df.to_csv(path_or_buf=response, index=False)
        return response
    elif forma == 'excel':
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
        response['Content-Disposition'] = 'attachment; filename=dose.xlsx'
        writer = pandas.ExcelWriter(response)
        df.to_excel(writer, 'Sheet1', index=False)
        writer.save()
        return response


@permission_required('main.view', 'login')
def search(request):
    devices = Device.objects.all()
    ord_dev = {}
    for dev in devices:
        key = deviceDict[dev.dtype].metadata["name"]
        if dev.version_fk is not None:
            key += "-" + dev.version_fk.version
        ord_dev[key] = ord_dev.get(key, []) + [dev]
    return (render(request, "search.html", {'devices' : ord_dev}))


# display list of all device order by type and version
@permission_required('main.view', 'login')
def view_devices(request):
    devices = Device.objects.all()
    ord_dev = {}
    for dev in devices:
        key = deviceDict[dev.dtype].metadata["name"]
        if dev.version_fk is not None:
            key += "-" + dev.version_fk.version
        ord_dev[key] = ord_dev.get(key, []) + [dev]
    return (render(request, "view_devices.html", {'devs' : ord_dev}))


# display list of all datafiles
@permission_required('main.view', 'login')
def view_datafiles(request):
    ctxt = {"files" : DataFile.objects.all()}
    return (render(request, "view_datafiles.html", ctxt))


# display list of data in one datafiles
@permission_required('main.view', 'login')
def view_data(request, id_datafile):
    dfile = get_object_or_404(DataFile, pk=id_datafile)
    dtype = dfile.device_fk.dtype
    data = deviceDict[dtype].objects.filter(file_fk=dfile).all()
    columns = deviceDict[dtype].metadata["columns"]
    resData = []
    coeff = None
    if len(data) > 0:
        coeff = Coefficient.objects.filter(device_fk=dfile.device_fk,
                                           start__lte=data[0].time).last()
    for d in data:
        tmp = [d.time]
        for col in columns:
            tmp.append(getattr(d, col["attr"]))
        tmp.append(d.flight_fk.num if d.flight_fk != None else "None")
        resData.append(tmp)
    ctxt = {"file" : dfile, "data" : resData, "coeff" : coeff,
        "columns" : [col["name"] for col in columns]}
    return (render(request, "view_data.html", ctxt))


# display list of all flightfiles
@permission_required('main.view', 'login')
def view_flightfiles(request):
    
    ctxt = {"files" : FlightFile.objects.exclude(user_fk=request.user).all(),
        "yfiles" : FlightFile.objects.filter(user_fk=request.user).all()}
    return (render(request, "view_flightfiles.html", ctxt))


# display list of flight in one flightfile
@permission_required('main.view', 'login')
def view_flights(request, id_flightfile):
    flight_file = get_object_or_404(FlightFile, pk = id_flightfile)
    devs = []
    for name, dv in deviceDict.items():
        vers = DeviceVersion.objects.filter(dtype=name).all()
        for ver in vers:
            devs.append(dv.metadata["name"] + '-' + ver.version)
        if len(vers) == 0:
            devs.append(dv.metadata["name"])
    ctxt = {
        "flights" : flight_file.flight_set.all(),
        "datafiles" : flight_file.datafile_set.all(),
        "file" : flight_file,
        "devices" : devs
        }
    if (request.method == "POST"):
        if (flight_file.user_fk == request.user or request.user.is_superuser):
            dtype = request.POST['dtype'].split('-')
            vers = None
            for device in deviceList:
                if (device.metadata['name'] == dtype[0]):
                    dev = device.__name__
            if (len(dtype) == 2):
                vers = DeviceVersion.objects.get(dtype=dev, version=dtype[1])
            file_ = request.FILES.getlist('datafile')[0]
            datafile, err = save_data_file(file_, dev, flight_file, vers)
            if (err != None):
                errors = ["File : " + file_.name + " " + err]
                return (render(request, "view_flights.html", 
                    dict(errors=errors, **ctxt)))
            l = idose_flights(datafile, flight_file.flight_set.all())
            IntegratedDose.objects.bulk_create(l)
            return (redirect('view_flights', id_flightfile))
        else:
           return (redirect('login'))
    else:
        return (render(request, "view_flights.html", ctxt))


# display data of one flight
@permission_required('main.view', 'login')
def view_flight(request, id_flight):
    flight = get_object_or_404(Flight, pk=id_flight)
    data = []
    for value in deviceList:
        flightdata = value.objects.filter(flight_fk=id_flight)
        if len(flightdata) != 0:
            columns = value.metadata["columns"]
            rows = []
            for d in flightdata:
                tmp = [d.time]
                for col in columns:
                    tmp.append(getattr(d, col["attr"]))
                rows.append(tmp)
            data.append({
                "device" : value.metadata["name"], "rows" : rows, 
                "columns" : [col["name"] for col in columns], 
                "idose" : IntegratedDose.objects.filter(
                    datafile_fk=flightdata[0].file_fk,
                    flight_fk=id_flight).first()
                })
    ctxt = {"flight" : flight, "data" : data, "file" : flight.file_fk}
    return (render(request, "view_flight.html", ctxt))
