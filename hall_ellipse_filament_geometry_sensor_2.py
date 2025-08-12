
from . import filament_switch_sensor
from . import ellipse_filament_wide_sensor_helper
from . import E_move_cuter


ADC_REPORT_TIME = 0.500
ADC_SAMPLE_TIME = 0.03
ADC_SAMPLE_COUNT = 15


class HallFilamentWidthSensor:
    def __init__(self, config):

        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.sensor = ellipse_filament_wide_sensor_helper.EllipseFilamentWideSensorHelper(config)

        self.MEASUREMENT_INTERVAL_MM = config.getfloat('measurement_interval', 5)
        self.nominal_filament_dia = config.getfloat(
            'default_nominal_filament_diameter', above=1)
        self.measurement_delay = config.getfloat('measurement_delay', above=0.)
        self.measurement_max_difference = config.getfloat('max_difference', 5)
        self.max_diameter = (self.nominal_filament_dia
                             + self.measurement_max_difference)
        self.min_diameter = (self.nominal_filament_dia
                             - self.measurement_max_difference)
        self.is_active = config.getboolean('enable', False)
        self.runout_dia_min = config.getfloat('min_diameter', 1.0)
        self.runout_dia_max = config.getfloat('max_diameter', self.max_diameter)
        self.is_log = config.getboolean('logging', False)
        self.check_e_pos_timeout = config.getfloat("check_e_pos_timeout", 1)
        if not (0.01 <= self.check_e_pos_timeout <= 5):
            raise config.error("invalid value check_e_pos_timeout\n\n value must be within\n 0.01 <= check_e_pos_timeout <= 5")
        self.binding_of_measurement = config.get('binding_of_measurement', 'extruder_stepper')
        if self.binding_of_measurement not in ('extruder_stepper', 'toolhead'):
            raise config.error("invalid value binding_of_measurement\n\n value must be 'extruder_stepper' or 'toolhead' ")
        self.get_real_epos = None  # method to obtain a coordinate that will snap to the measurement

        self.use_move_cuter = config.getboolean('use_e_move_cuter', False)
        if self.use_move_cuter:
            self.move_cuter = E_move_cuter.EMoveCuter(config)
            self.move_cuter.set_in_move_callback(self.extrude_factor_update_event)
            self.set_extrude_factor = self.move_cuter.set_extrude_factor
        else:
            self.set_extrude_factor = self.set_extrude_factor_by_M221

        # Use the current diameter instead of nominal while the first
        # measurement isn't in place
        self.use_current_dia_while_delay = config.getboolean(
            'use_current_dia_while_delay', False)
        # filament array [position, filamentWidth]
        self.filament_array = []
        self.firstExtruderUpdatePosition = 0
        self.filament_width = self.nominal_filament_dia
        # printer objects
        self.toolhead = self.ppins = self.mcu_adc = None
        self.printer.register_event_handler("klippy:ready", self.handle_ready)
        # extrude factor updating
        self.filament_array_update_timer = self.reactor.register_timer(
            self.prime_event)
        # Register commands
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command('QUERY_FILAMENT_WIDTH', self.cmd_M407)
        self.gcode.register_command('RESET_FILAMENT_WIDTH_SENSOR',
                                    self.cmd_ClearFilamentArray)
        self.gcode.register_command('DISABLE_FILAMENT_WIDTH_SENSOR',
                                    self.cmd_M406)
        self.gcode.register_command('ENABLE_FILAMENT_WIDTH_SENSOR',
                                    self.cmd_M405)
        self.gcode.register_command('QUERY_RAW_FILAMENT_WIDTH',
                                    self.cmd_Get_Raw_Values)
        self.gcode.register_command('ENABLE_FILAMENT_WIDTH_LOG',
                                    self.cmd_log_enable)
        self.gcode.register_command('DISABLE_FILAMENT_WIDTH_LOG',
                                    self.cmd_log_disable)

        self.runout_helper = filament_switch_sensor.RunoutHelper(config)
        self.gcode.respond_info("мой любимый датчик инициализировался !!!")

    def handle_ready(self):
        # Load printer objects
        self.toolhead = self.printer.lookup_object('toolhead')
        if self.binding_of_measurement == "toolhead":
            self.get_real_epos = lambda *args:self.toolhead.get_position()[3]
        elif self.binding_of_measurement == "extruder_stepper":
            extruder = self.printer.lookup_object('extruder')
            if extruder.extruder_stepper is None:
                raise self.printer.config_error("какого фига этот модуль подключен, когда фидер не определен?!")
            self.get_real_epos = extruder.extruder_stepper.stepper.get_commanded_position
        else:
            raise self.printer.config_error("invalid value binding_of_measurement\n value must be 'extruder_stepper' or 'toolhead' \n\n unforeseen error")

        # Start filament array update timer
        self.reactor.update_timer(self.filament_array_update_timer, self.reactor.NOW)

    def prime_event(self, eventtime):
        # Update filament array for lastFilamentWidthReading
        self.update_filament_array(self.get_real_epos())
        # Check runout
        self.runout_helper.note_filament_present(eventtime, self.sensor.check_for_virtual_f_swich_sensor())

        if not self.use_move_cuter:
            self.extrude_factor_update_event()

        if self.is_active:
            return eventtime + self.check_e_pos_timeout
        else:
            return self.reactor.NEVER

    def update_filament_array(self, last_epos):
        if self.sensor.use_internal_delay:
            self.sensor.update_internal_arrais(last_epos)
        # Fill array
        if len(self.filament_array) > 0:
            # Get last reading position in array & calculate next
            # reading position
            next_reading_position = (self.filament_array[-1][0] + self.MEASUREMENT_INTERVAL_MM)
            if next_reading_position <= (last_epos + self.measurement_delay):
                sensor_value = self.sensor(last_epos)
                self.filament_array.append([last_epos + self.measurement_delay, sensor_value])
                if self.is_log:
                    self.gcode.respond_info(f"Filament width: {sensor_value}\n filament_aray_lenth: {len(self.filament_array)}")

        else:
            # add first item to array
            self.filament_array.append([self.measurement_delay + last_epos,
                                        self.sensor(last_epos)])
            self.firstExtruderUpdatePosition = (self.measurement_delay
                                                + last_epos)

    def extrude_factor_update_event(self):
        # Update extrude factor
        pos = self.toolhead.get_position()
        last_epos = pos[3]

        # Does filament exists
        if 0.8 > 0.5:
            if len(self.filament_array) > 0:
                # Get first position in filament array
                pending_position = self.filament_array[0][0]
                if pending_position <= last_epos:
                    # Get first item in filament_array queue
                    item = self.filament_array.pop(0)
                    self.filament_width = item[1]
                    if self.is_log:
                        self.gcode.respond_info(f"привет от датчика W={self.filament_width}")
                else:
                    if (self.use_current_dia_while_delay
                        and (self.firstExtruderUpdatePosition
                             == pending_position)):
                        self.filament_width = self.sensor(last_epos)
                    elif self.firstExtruderUpdatePosition == pending_position:
                        self.filament_width = self.nominal_filament_dia
                if self.min_diameter <= self.filament_width <= self.max_diameter:
                    self.set_extrude_factor((self.nominal_filament_dia / self.filament_width) ** 2)
                else:
                    self.set_extrude_factor(1)  # M221 S100
        else:
            self.set_extrude_factor(1)  # M221 S100
            self.filament_array = []

    def set_extrude_factor_by_M221(self, extrude_factor):
        percentage = (extrude_factor * 100) // 1
        if extrude_factor % 0.01 >= 0.005:
            percentage += 1
        self.gcode.run_script("M221 S" + str(percentage))

    def cmd_M407(self, gcmd):
        gcmd.respond_info(str(self.sensor))

    def cmd_ClearFilamentArray(self, gcmd):
        self.filament_array = []
        gcmd.respond_info("Filament width measurements cleared!")
        # Set extrude multiplier to 100%
        self.set_extrude_factor(1)  # M221 S100

    def cmd_M405(self, gcmd):
        response = "Filament width sensor Turned On"
        if self.is_active:
            response = "Filament width sensor is already On"
        else:
            self.is_active = True
            # Start extrude factor update timer
            self.reactor.update_timer(self.filament_array_update_timer,
                                      self.reactor.NOW)
        gcmd.respond_info(response)

    def cmd_M406(self, gcmd):
        response = "Filament width sensor Turned Off"
        if not self.is_active:
            response = "Filament width sensor is already Off"
        else:
            self.is_active = False
            # Stop extrude factor update timer
            self.reactor.update_timer(self.filament_array_update_timer,
                                      self.reactor.NEVER)
            # Clear filament array
            self.filament_array = []
            # Set extrude multiplier to 100%
            self.set_extrude_factor(1)  # M221 S100
        gcmd.respond_info(response)

    def cmd_Get_Raw_Values(self, gcmd):
        self.sensor.get_raw_values(gcmd)

    def get_status(self, eventtime):
        result = self.sensor.get_status_dict()
        result.update({'is_active': self.is_active})
        return result

    def cmd_log_enable(self, gcmd):
        self.is_log = True
        gcmd.respond_info("Filament width logging Turned On")

    def cmd_log_disable(self, gcmd):
        self.is_log = False
        gcmd.respond_info("Filament width logging Turned Off")


def load_config(config):
    return HallFilamentWidthSensor(config)
