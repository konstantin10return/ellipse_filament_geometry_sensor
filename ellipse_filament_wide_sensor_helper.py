

from . import hall_filament_geometry_sensor_helper


class EllipseFilamentWideSensorHelper:
    def __init__(self, config):
        self.internal_delay = config.getfloat('internel_delay', 14.6)
        self.use_internal_delay = config.getboolean('use_internal_delay', False)

        if not self.use_internal_delay:
            self.sensor1 = hall_filament_geometry_sensor_helper.HallFilamentWideSensorHelper(config, 's1_')
            self.sensor2 = hall_filament_geometry_sensor_helper.HallFilamentWideSensorHelper(config, 's2_')
        else:
            self.sensor1 = hall_filament_geometry_sensor_helper.HallFilamentWideSensorHelperWithInternalAra(config, 's1_', self.internal_delay * 2)
            self.sensor2 = hall_filament_geometry_sensor_helper.HallFilamentWideSensorHelperWithInternalAra(config, 's2_', self.internal_delay)

        self.sensor3 = hall_filament_geometry_sensor_helper.HallFilamentWideSensorHelper(config, 's3_')

        self.d1 = self.d2 = self.d3 = 0

        self.nominal_filament_dia = config.getfloat(
            'default_nominal_filament_diameter', above=1)

        self.d1 = self.d2 = self.d3 = self.nominal_filament_dia / 2
        self.a = self.b = self.nominal_filament_dia / 2
        self.measurement_max_difference = config.getfloat('max_difference', 0.2)
        self.max_diameter = (self.nominal_filament_dia
                             + self.measurement_max_difference)
        self.min_diameter = (self.nominal_filament_dia
                             - self.measurement_max_difference)
        self.runout_dia_min = config.getfloat('min_diameter', 1.0)
        self.runout_dia_max = config.getfloat('max_diameter', self.max_diameter)
        self.runout_r_min = self.runout_dia_min / 2

        self.precision = config.getfloat('precision', 100)
        if self.precision < 1:
            raise config.error('"precision" в секции "hall_elipse_filament_geometry_sensor" не может быть ментше 1')

    def update_internal_arrais(self, last_epos):
        self.sensor1.update_filament_array(last_epos)
        self.sensor2.update_filament_array(last_epos)

    def __call__(self, last_epos=None):
        if last_epos is None:
            self.d1, self.d2, self.d3 = (self.sensor1.diameter, self.sensor2.diameter, self.sensor3.diameter)
        else:
            self.d1, self.d2, self.d3 = (self.sensor1.get_value(last_epos), self.sensor2.get_value(last_epos), self.sensor3.get_value(last_epos))
        r1, r3, r2 = sorted([self.d1 / 2, self.d2 / 2, self.d3 / 2], reverse=True)
        # тут вычисления !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        if r3 < self.runout_r_min or r2 < self.runout_r_min or r1 < self.runout_r_min:
            return (self.a * self.b) ** 0.5 * 2
        if r1 == r2:
            if r2 == r3:
                self.a, self.b = r1, r1
                return r1 * 2
            r1, r3 = r3, r1
        if r2 == r3:
            b = (0.75 * r2 ** 2 / (1 - (0.25 * r2 ** 2 / r1 ** 2))) ** 0.5
            self.b, self.a = sorted([r1, b])
            return (self.a * self.b) ** 0.5 * 2
        # тут вычисления !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        max_c = (0.75 * r1 ** 2 / (1 - (0.25 * r1 ** 2 / r2 ** 2))) * self.precision * self.precision
        r1, r2, r3 = [i * self.precision for i in (r1, r2, r3)]
        perfect_c = 0
        perfect_delta_d = 10 ** 8
        d = ()

        p1 = 12 * (((r1 ** 4) * (r2 ** 2)) + ((r1 ** 2) * (r2 ** 4)))
        p2 = 15 * ((r1 * r2) ** 4)
        p3 = 12 * ((r1 * r2) ** 3)
        p4 = (r1 * r2) ** 2
        p5 = (r1 ** 2) + (r2 ** 2)
        p6 = 16 * ((r1 ** 4) + p4 + (r2 ** 4))
        p7 = 2 * p1
        p8 = 9 * ((r1 * r2) ** 4)

        k1 = 12 * (((r1 ** 4) * (r3 ** 2)) + ((r1 ** 2) * (r3 ** 4)))
        k2 = 15 * ((r1 * r3) ** 4)
        k3 = 12 * ((r1 * r3) ** 3)
        k4 = (r1 * r3) ** 2
        k5 = (r1 ** 2) + (r3 ** 2)
        k6 = 16 * ((r1 ** 4) + k4 + (r3 ** 4))
        k7 = 2 * k1
        k8 = 9 * ((r1 * r3) ** 4)

        for c in range(int(r1 ** 2) - 1, int(max_c) + 2):
            d1 = (((p1 * (c ** 2)) - (p2 * c) + (p3 * c * ((p4 - (p5 * c) + (c ** 2)) ** 0.5))) /
                  (p6 * (c ** 2) - (p7 * c) + p8)).real
            d2 = (((k1 * (c ** 2)) - (k2 * c) - (k3 * c * ((k4 - (k5 * c) + (c ** 2)) ** 0.5))) /
                  (k6 * (c ** 2) - (k7 * c) + k8)).real
            if d1 <= 0 or d2 <= 0:
                continue
            if d1 >= c:
                continue
            delta = d1 - d2
            if delta < 0:
                delta = -delta
            if delta < perfect_delta_d:
                perfect_c = c
                perfect_delta_d = delta
                d = (d1, d2)
        self.a, self.b = (perfect_c ** 0.5) / self.precision, (((d[0] + d[1]) / 2) ** 0.5) / self.precision
        # тут вычисления !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        return (self.a * self.b) ** 0.5 * 2

    def check_for_virtual_f_swich_sensor(self):
        if self.sensor1.diameter < self.runout_dia_min:
            return False
        if self.sensor1.diameter > self.runout_dia_max:
            return False
        if self.sensor2.diameter < self.runout_dia_min:
            return False
        if self.sensor2.diameter > self.runout_dia_max:
            return False
        if self.sensor3.diameter < self.runout_dia_min:
            return False
        if self.sensor3.diameter > self.runout_dia_max:
            return False
        if self.a * 2 > self.runout_dia_max:
            return False
        if self.b * 2 < self.runout_dia_min:
            return False
        return True  # if it's ok

    def __str__(self):
        if (self.sensor1.diameter < self.runout_dia_min or
                self.sensor2.diameter < self.runout_dia_min or self.sensor3.diameter < self.runout_dia_min):
            return ('sensor value is less than the minimum value! ' +
                    f'{self.sensor1.SENSOR_PREFIX}diameter={self.sensor1.diameter} ' +
                    f'{self.sensor2.SENSOR_PREFIX}diameter={self.sensor2.diameter} ' +
                    f'{self.sensor3.SENSOR_PREFIX}diameter={self.sensor3.diameter} ')
        virtual_diameter = self.__call__()
        return f'a={self.a}  b={self.b}  virtual_diameter={virtual_diameter}  ' + (f'{self.sensor1.SENSOR_PREFIX}diameter={self.d1} ' +
                                                                                   f'{self.sensor2.SENSOR_PREFIX}diameter={self.d2} ' +
                                                                                   f'{self.sensor3.SENSOR_PREFIX}diameter={self.d3} ')

    def get_raw_values(self, gcmd):
        gcmd.respond_info('PREFIX=' + self.sensor1.SENSOR_PREFIX + ' ' + self.sensor1.Get_Raw_Values())
        gcmd.respond_info('PREFIX=' + self.sensor2.SENSOR_PREFIX + ' ' + self.sensor2.Get_Raw_Values())
        gcmd.respond_info('PREFIX=' + self.sensor3.SENSOR_PREFIX + ' ' + self.sensor3.Get_Raw_Values())

    def get_status_dict(self):
        rez = dict()
        rez.update({f'{self.sensor1.SENSOR_PREFIX}diameter': str(self.sensor1.diameter)})
        rez.update({f'{self.sensor2.SENSOR_PREFIX}diameter': str(self.sensor2.diameter)})
        rez.update({f'{self.sensor3.SENSOR_PREFIX}diameter': str(self.sensor3.diameter)})
        return rez
