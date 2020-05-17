from math import floor

from datetime import datetime
import time
from interruptingcow import timeout

from exceptions import DeviceTimeoutError
from mqtt import MqttMessage
from workers.base import BaseWorker

REQUIREMENTS = ["bluepy"]


# Bluepy might need special settings
# sudo setcap 'cap_net_raw,cap_net_admin+eip' /usr/local/lib/python3.6/dist-packages/bluepy/bluepy-helper


class MiscaleWorker(BaseWorker):

    SCAN_TIMEOUT = 5

    def getAge(self, d1):
        d1 = datetime.strptime(str(d1), "%Y-%m-%d")
        d2 = datetime.strptime(datetime.today().strftime("%Y-%m-%d"), "%Y-%m-%d")
        return abs((d2 - d1).days) / 365

    def status_update(self):
        results = self._get_data()

        messages = [
            MqttMessage(
                topic=self.format_topic("weight/" + results.unit),
                payload=results.weight,
            )
        ]
        if results.impedance:
            messages.append(
                MqttMessage(
                    topic=self.format_topic("impedance"), payload=results.impedance
                )
            )
        if results.midatetime:
            messages.append(
                MqttMessage(
                    topic=self.format_topic("midatetime"), payload=results.midatetime
                )
            )

        if hasattr(self, "users"):
            for key, item in self.users.items():
                if (
                    item["weight_template"]["min"]
                    <= results.weight
                    <= item["weight_template"]["max"]
                ):
                    user = key
                    sex = item["sex"]
                    height = item["height"]
                    age = self.getAge(item["dob"])

                    lib = bodyMetrics(results.weight, results.unit, height, age, sex, results.impedance)
                    metrics = {
                        "weight": float("{:.2f}".format(results.weight)),
                        "bmi": float("{:.2f}".format(lib.getBMI())),
                        "basal_metabolism": float("{:.2f}".format(lib.getBMR())),
                        "visceral_fat": float("{:.2f}".format(lib.getVisceralFat())),
                        "user": user,
                    }

                    if lib.is_impedance_value_valid():
                        metrics["impedance"] = lib.impedance
                        metrics["lean_body_mass"] = float(
                            "{:.2f}".format(lib.getLBMCoefficient())
                        )
                        metrics["body_fat"] = float(
                            "{:.2f}".format(lib.getFatPercentage())
                        )
                        metrics["water"] = float(
                            "{:.2f}".format(lib.getWaterPercentage())
                        )
                        metrics["bone_mass"] = float("{:.2f}".format(lib.getBoneMass()))
                        metrics["muscle_mass"] = float(
                            "{:.2f}".format(lib.getMuscleMass())
                        )
                        metrics["protein"] = float(
                            "{:.2f}".format(lib.getProteinPercentage())
                        )

                    if results.midatetime:
                        metrics["timestamp"] = results.midatetime

                    messages.append(
                        MqttMessage(
                            topic=self.format_topic("users/" + user), payload=metrics
                        )
                    )

        return messages

    def _get_data(self):
        from bluepy import btle

        scan_processor = ScanProcessor(self.mac)
        scanner = btle.Scanner().withDelegate(scan_processor)
        scanner.scan(self.SCAN_TIMEOUT, passive=True)

        with timeout(
            self.SCAN_TIMEOUT,
            exception=DeviceTimeoutError(
                "Retrieving data from {} device {} timed out after {} seconds".format(
                    repr(self), self.mac, self.SCAN_TIMEOUT
                )
            ),
        ):
            while not scan_processor.ready:
                time.sleep(1)
            return scan_processor.results

        return scan_processor.results


class ScanProcessor:
    def __init__(self, mac):
        self._ready = False
        self._mac = mac
        self._results = MiWeightScaleData()

    def handleDiscovery(self, dev, isNewDev, _):
        if dev.addr == self.mac.lower() and isNewDev:
            for (sdid, desc, data) in dev.getScanData():

                # Xiaomi Scale V1
                if data.startswith("1d18") and sdid == 22:
                    measunit = data[4:6]
                    measured = int((data[8:10] + data[6:8]), 16) * 0.01
                    unit = ""

                    if measunit.startswith(("03", "b3")):
                        unit = "lbs"
                    elif measunit.startswith(("12", "b2")):
                        unit = "jin"
                    elif measunit.startswith(("22", "a2")):
                        unit = "kg"
                        measured = measured / 2

                    self.results.weight = round(measured, 2)
                    self.results.unit = unit

                    self.ready = True

                # Xiaomi Scale V2
                if data.startswith("1b18") and sdid == 22:
                    measunit = data[4:6]
                    measured = int((data[28:30] + data[26:28]), 16) * 0.01
                    unit = ""

                    if measunit == "03":
                        unit = "lbs"
                    elif measunit == "02":
                        unit = "kg"
                        measured = measured / 2

                    midatetime = datetime.strptime(
                        str(int((data[10:12] + data[8:10]), 16))
                        + " "
                        + str(int((data[12:14]), 16))
                        + " "
                        + str(int((data[14:16]), 16))
                        + " "
                        + str(int((data[16:18]), 16))
                        + " "
                        + str(int((data[18:20]), 16))
                        + " "
                        + str(int((data[20:22]), 16)),
                        "%Y %m %d %H %M %S",
                    )

                    self.results.weight = round(measured, 2)
                    self.results.unit = unit
                    self.results.impedance = int((data[24:26] + data[22:24]), 16)
                    self.results.midatetime = str(midatetime)

                    self.ready = True

    @property
    def mac(self):
        return self._mac

    @property
    def ready(self):
        return self._ready

    @ready.setter
    def ready(self, var):
        self._ready = var

    @property
    def results(self):
        return self._results


class MiWeightScaleData:
    def __init__(self):
        self._weight = None
        self._unit = None
        self._midatetime = None
        self._impedance = None

    @property
    def weight(self):
        return self._weight

    @weight.setter
    def weight(self, var):
        self._weight = var

    @property
    def unit(self):
        return self._unit

    @unit.setter
    def unit(self, var):
        self._unit = var

    @property
    def midatetime(self):
        return self._midatetime

    @midatetime.setter
    def midatetime(self, var):
        self._midatetime = var

    @property
    def impedance(self):
        return self._impedance

    @impedance.setter
    def impedance(self, var):
        self._impedance = var


class bodyMetrics:
    def __init__(self, weight, unit, height, age, sex, impedance):
        # Calculations need weight to be in kg, check unit and convert to kg if needed
        if unit == "lbs":
            weight = weight / 2.20462

        self.weight = weight
        self.height = height
        self.age = age
        self.sex = sex
        self.impedance = impedance

        # Check for potential out of boundaries
        if self.height > 220:
            raise Exception("Height is too high (limit: >220cm)")
        elif weight < 10 or weight > 200:
            raise Exception(
                "Weight is either too low or too high (limits: <10kg and >200kg)"
            )
        elif age > 99:
            raise Exception("Age is too high (limit >99 years)")

    def is_impedance_value_valid(self):
        # Impedance could be 0 if someone gets off the MiScale just after the weight measurement, but before the
        # impedance measurement. Impedance could be high value (usually 65533), for example when someone
        # is not barefoot.
        return isinstance(self.impedance, int) and 0 < self.impedance <= 3000

    # Set the value to a boundary if it overflows
    def checkValueOverflow(self, value, minimum, maximum):
        if value < minimum:
            return minimum
        elif value > maximum:
            return maximum
        else:
            return value

    # Get LBM coefficient (with impedance)
    def getLBMCoefficient(self):
        if not self.is_impedance_value_valid():
            raise Exception("Impedance is not valid, LBM could not be calculated.")

        lbm = (self.height * 9.058 / 100) * (self.height / 100)
        lbm += self.weight * 0.32 + 12.226
        lbm -= self.impedance * 0.0068
        lbm -= self.age * 0.0542
        return lbm

    # Get BMR
    def getBMR(self):
        if self.sex == "female":
            bmr = 864.6 + self.weight * 10.2036
            bmr -= self.height * 0.39336
            bmr -= self.age * 6.204
        else:
            bmr = 877.8 + self.weight * 14.916
            bmr -= self.height * 0.726
            bmr -= self.age * 8.976

        # Capping
        if self.sex == "female" and bmr > 2996:
            bmr = 5000
        elif self.sex == "male" and bmr > 2322:
            bmr = 5000
        return self.checkValueOverflow(bmr, 500, 10000)

    # Get BMR scale
    def getBMRScale(self):
        coefficients = {
            "female": {12: 34, 15: 29, 17: 24, 29: 22, 50: 20, 120: 19},
            "male": {12: 36, 15: 30, 17: 26, 29: 23, 50: 21, 120: 20},
        }

        for age, coefficient in coefficients[self.sex].items():
            if self.age < age:
                return [self.weight * coefficient]
                break

    # Get fat percentage
    def getFatPercentage(self):
        # Set a constant to remove from LBM
        if self.sex == "female" and self.age <= 49:
            const = 9.25
        elif self.sex == "female" and self.age > 49:
            const = 7.25
        else:
            const = 0.8

        # Calculate body fat percentage
        LBM = self.getLBMCoefficient()

        if self.sex == "male" and self.weight < 61:
            coefficient = 0.98
        elif self.sex == "female" and self.weight > 60:
            coefficient = 0.96
            if self.height > 160:
                coefficient *= 1.03
        elif self.sex == "female" and self.weight < 50:
            coefficient = 1.02
            if self.height > 160:
                coefficient *= 1.03
        else:
            coefficient = 1.0
        fatPercentage = (1.0 - (((LBM - const) * coefficient) / self.weight)) * 100

        # Capping body fat percentage
        if fatPercentage > 63:
            fatPercentage = 75
        return self.checkValueOverflow(fatPercentage, 5, 75)

    # Get fat percentage scale
    def getFatPercentageScale(self):
        # The included tables where quite strange, maybe bogus, replaced them with better ones...
        scales = [
            {"min": 0, "max": 20, "female": [18, 23, 30, 35], "male": [8, 14, 21, 25]},
            {
                "min": 21,
                "max": 25,
                "female": [19, 24, 30, 35],
                "male": [10, 15, 22, 26],
            },
            {
                "min": 26,
                "max": 30,
                "female": [20, 25, 31, 36],
                "male": [11, 16, 21, 27],
            },
            {
                "min": 31,
                "max": 35,
                "female": [21, 26, 33, 36],
                "male": [13, 17, 25, 28],
            },
            {
                "min": 46,
                "max": 40,
                "female": [22, 27, 34, 37],
                "male": [15, 20, 26, 29],
            },
            {
                "min": 41,
                "max": 45,
                "female": [23, 28, 35, 38],
                "male": [16, 22, 27, 30],
            },
            {
                "min": 46,
                "max": 50,
                "female": [24, 30, 36, 38],
                "male": [17, 23, 29, 31],
            },
            {
                "min": 51,
                "max": 55,
                "female": [26, 31, 36, 39],
                "male": [19, 25, 30, 33],
            },
            {
                "min": 56,
                "max": 100,
                "female": [27, 32, 37, 40],
                "male": [21, 26, 31, 34],
            },
        ]

        for scale in scales:
            if self.age >= scale["min"] and self.age <= scale["max"]:
                return scale[self.sex]

    # Get water percentage
    def getWaterPercentage(self):
        waterPercentage = (100 - self.getFatPercentage()) * 0.7

        if waterPercentage <= 50:
            coefficient = 1.02
        else:
            coefficient = 0.98

        # Capping water percentage
        if waterPercentage * coefficient >= 65:
            waterPercentage = 75
        return self.checkValueOverflow(waterPercentage * coefficient, 35, 75)

    # Get water percentage scale
    def getWaterPercentageScale(self):
        return [53, 67]

    # Get bone mass
    def getBoneMass(self):
        if self.sex == "female":
            base = 0.245691014
        else:
            base = 0.18016894

        boneMass = (base - (self.getLBMCoefficient() * 0.05158)) * -1

        if boneMass > 2.2:
            boneMass += 0.1
        else:
            boneMass -= 0.1

        # Capping boneMass
        if self.sex == "female" and boneMass > 5.1:
            boneMass = 8
        elif self.sex == "male" and boneMass > 5.2:
            boneMass = 8
        return self.checkValueOverflow(boneMass, 0.5, 8)

    # Get bone mass scale
    def getBoneMassScale(self):
        scales = [
            {
                "female": {"min": 60, "optimal": 2.5},
                "male": {"min": 75, "optimal": 3.2},
            },
            {
                "female": {"min": 45, "optimal": 2.2},
                "male": {"min": 69, "optimal": 2.9},
            },
            {"female": {"min": 0, "optimal": 1.8}, "male": {"min": 0, "optimal": 2.5}},
        ]

        for scale in scales:
            if self.weight >= scale[self.sex]["min"]:
                return [scale[self.sex]["optimal"] - 1, scale[self.sex]["optimal"] + 1]

    # Get muscle mass
    def getMuscleMass(self):
        muscleMass = (
            self.weight
            - ((self.getFatPercentage() * 0.01) * self.weight)
            - self.getBoneMass()
        )

        # Capping muscle mass
        if self.sex == "female" and muscleMass >= 84:
            muscleMass = 120
        elif self.sex == "male" and muscleMass >= 93.5:
            muscleMass = 120

        return self.checkValueOverflow(muscleMass, 10, 120)

    # Get muscle mass scale
    def getMuscleMassScale(self):
        scales = [
            {"min": 170, "female": [36.5, 42.5], "male": [49.5, 59.4]},
            {"min": 160, "female": [32.9, 37.5], "male": [44.0, 52.4]},
            {"min": 0, "female": [29.1, 34.7], "male": [38.5, 46.5]},
        ]

        for scale in scales:
            if self.height >= scale["min"]:
                return scale[self.sex]

    # Get Visceral Fat
    def getVisceralFat(self):
        if self.sex == "female":
            if self.weight > (13 - (self.height * 0.5)) * -1:
                subsubcalc = (
                    (self.height * 1.45) + (self.height * 0.1158) * self.height
                ) - 120
                subcalc = self.weight * 500 / subsubcalc
                vfal = (subcalc - 6) + (self.age * 0.07)
            else:
                subcalc = 0.691 + (self.height * -0.0024) + (self.height * -0.0024)
                vfal = (
                    (((self.height * 0.027) - (subcalc * self.weight)) * -1)
                    + (self.age * 0.07)
                    - self.age
                )
        else:
            if self.height < self.weight * 1.6:
                subcalc = (
                    (self.height * 0.4) - (self.height * (self.height * 0.0826))
                ) * -1
                vfal = ((self.weight * 305) / (subcalc + 48)) - 2.9 + (self.age * 0.15)
            else:
                subcalc = 0.765 + self.height * -0.0015
                vfal = (
                    (((self.height * 0.143) - (self.weight * subcalc)) * -1)
                    + (self.age * 0.15)
                    - 5.0
                )

        return self.checkValueOverflow(vfal, 1, 50)

    # Get visceral fat scale
    def getVisceralFatScale(self):
        return [10, 15]

    # Get BMI
    def getBMI(self):
        return self.checkValueOverflow(
            self.weight / ((self.height / 100) * (self.height / 100)), 10, 90
        )

    # Get BMI scale
    def getBMIScale(self):
        # Replaced library's version by mi fit scale, it seems better
        return [18.5, 25, 28, 32]

    # Get ideal weight (just doing a reverse BMI, should be something better)
    def getIdealWeight(self):
        return self.checkValueOverflow(
            (22 * self.height) * self.height / 10000, 5.5, 198
        )

    # Get ideal weight scale (BMI scale converted to weights)
    def getIdealWeightScale(self):
        scale = []
        for bmiScale in self.getBMIScale():
            scale.append((bmiScale * self.height) * self.height / 10000)
        return scale

    # Get fat mass to ideal (guessing mi fit formula)
    def getFatMassToIdeal(self):
        mass = (self.weight * (self.getFatPercentage() / 100)) - (
            self.weight * (self.getFatPercentageScale()[2] / 100)
        )
        if mass < 0:
            return {"type": "to_gain", "mass": mass * -1}
        else:
            return {"type": "to_lose", "mass": mass}

    # Get protetin percentage (warn: guessed formula)
    def getProteinPercentage(self):
        proteinPercentage = 100 - (floor(self.getFatPercentage() * 100) / 100)
        proteinPercentage -= floor(self.getWaterPercentage() * 100) / 100
        proteinPercentage -= floor((self.getBoneMass() / self.weight * 100) * 100) / 100
        return proteinPercentage

    # Get protein scale (hardcoded in mi fit)
    def getProteinPercentageScale(self):
        return [16, 20]

    # Get body type (out of nine possible)
    def getBodyType(self):
        if self.getFatPercentage() > self.getFatPercentageScale()[2]:
            factor = 0
        elif self.getFatPercentage() < self.getFatPercentageScale()[1]:
            factor = 2
        else:
            factor = 1

        if self.getMuscleMass() > self.getMuscleMassScale()[1]:
            return 2 + (factor * 3)
        elif self.getMuscleMass() < self.getMuscleMassScale()[0]:
            return factor * 3
        else:
            return 1 + (factor * 3)

    # Return body type scale
    def getBodyTypeScale(self):
        return [
            "obese",
            "overweight",
            "thick-set",
            "lack-exerscise",
            "balanced",
            "balanced-muscular",
            "skinny",
            "balanced-skinny",
            "skinny-muscular",
        ]
