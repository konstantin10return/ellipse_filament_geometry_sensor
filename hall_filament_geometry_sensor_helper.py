ADC_REPORT_TIME = 0.900
ADC_SAMPLE_TIME = 0.03
ADC_SAMPLE_COUNT = 15

MEASUREMENT_INTERVAL_MM = 0.05


class HallFilamentWideSensorHelper:
    def __init__(self, config, SENSOR_PREFIX):
        self.printer = config.get_printer()
        self.pin1 = config.get(SENSOR_PREFIX + 'adc1_pin')
        self.pin2 = config.get(SENSOR_PREFIX + 'adc2_pin')
        self.dia1 = config.getfloat(SENSOR_PREFIX + 'Cal_dia1', 1.5)
        self.dia2 = config.getfloat(SENSOR_PREFIX + 'Cal_dia2', 2.0)
        self.rawdia1 = config.getint(SENSOR_PREFIX + 'Raw_dia1', 9500)
        self.rawdia2 = config.getint(SENSOR_PREFIX + 'Raw_dia2', 10500)
        self.nominal_filament_dia = config.getfloat(
            'default_nominal_filament_diameter', above=1)
        
        self.diameter = self.nominal_filament_dia
        self.ppins = self.printer.lookup_object('pins')
        self.mcu_adc = self.ppins.setup_pin('adc', self.pin1)
        
        self.mcu_adc.setup_adc_sample(ADC_SAMPLE_TIME, ADC_SAMPLE_COUNT)
        self.mcu_adc.setup_adc_callback(ADC_REPORT_TIME, self.adc_callback)
        self.mcu_adc2 = self.ppins.setup_pin('adc', self.pin2)
        self.mcu_adc2.setup_adc_sample(ADC_SAMPLE_TIME, ADC_SAMPLE_COUNT)
        self.mcu_adc2.setup_adc_callback(ADC_REPORT_TIME, self.adc2_callback)
        self.lastFilamentWidthReading = 0
        self.lastFilamentWidthReading2 = 0
        self.SENSOR_PREFIX = SENSOR_PREFIX

    def adc_callback(self, read_time, read_value):
        # read sensor value
        self.lastFilamentWidthReading = round(read_value * 10000)

    def adc2_callback(self, read_time, read_value):
        # read sensor value
        self.lastFilamentWidthReading2 = round(read_value * 10000)
        # calculate diameter
        diameter_new = round((self.dia2 - self.dia1) /
                             (self.rawdia2 - self.rawdia1) *
                             ((self.lastFilamentWidthReading + self.lastFilamentWidthReading2)
                              - self.rawdia1) + self.dia1, 4)
        self.diameter = (5.0 * self.diameter + diameter_new) / 6

    def Get_Raw_Values(self):
        response = "ADC1="
        response += str(self.lastFilamentWidthReading)
        response += (" ADC2=" + str(self.lastFilamentWidthReading2))
        response += (" RAW=" +
                     str(self.lastFilamentWidthReading
                         + self.lastFilamentWidthReading2))
        return response

    def get_value(self, *args):
        return self.diameter


# ---------------------------------------------------------------------------------------


class HallFilamentWideSensorHelperWithInternalAra(HallFilamentWideSensorHelper):
    def __init__(self, config, SENSOR_PREFIX, internal_measurement_delay):
        super().__init__(config, SENSOR_PREFIX)
        self.measurement_delay = internal_measurement_delay
        # filament array [position, filamentWidth]
        self.filament_array = []
        self.filament_width_data = None
        self.firstExtruderUpdatePosition = 0

    def update_filament_array(self, last_epos):
        # Fill array
        if len(self.filament_array) > 0:
            # Get last reading position in array & calculate next
            # reading position
            next_reading_position = (self.filament_array[-1][0] + MEASUREMENT_INTERVAL_MM)
            if next_reading_position <= (last_epos + self.measurement_delay):
                self.filament_array.append([last_epos + self.measurement_delay, self.diameter])

        else:
            # add first item to array
            self.filament_array.append([self.measurement_delay + last_epos,
                                        self.diameter])
            self.firstExtruderUpdatePosition = (self.measurement_delay
                                                + last_epos)

    def delite_spam(self, last_epos):
        if len(self.filament_array) == 0:
            return None

        while len(self.filament_array) > 0:
            pending_position = self.filament_array[0][0]
            if pending_position <= last_epos:
                # Get first item in filament_array queue
                self.filament_width_data = self.filament_array.pop(0)
            else:
                break

    def get_value(self, last_epos):
        self.delite_spam(last_epos)
        if self.filament_width_data is not None:
            return self.filament_width_data[-1]
        if len(self.filament_array) != 0:
            return self.filament_array[0][-1]
        return self.diameter
