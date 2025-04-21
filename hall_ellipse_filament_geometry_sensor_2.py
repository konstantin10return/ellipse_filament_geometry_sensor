
from . import ellipse_filament_wide_sensor_helper


ADC_REPORT_TIME = 0.500
ADC_SAMPLE_TIME = 0.03
ADC_SAMPLE_COUNT = 15


class HallFilamentWidthSensor:
    def __init__(self, config):

        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.sensor = ellipse_filament_wide_sensor_helper.EllipseFilamentWideSensorHelper(config)

        self.MEASUREMENT_INTERVAL_MM = config.getint('measurement_interval', 5)
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
        self.extrude_factor_update_timer = self.reactor.register_timer(
            self.extrude_factor_update_event)
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
        self.gcode.respond_info("мой любимый датчик инициализировался !!!")

    def handle_ready(self):
        # Load printer objects
        self.toolhead = self.printer.lookup_object('toolhead')

        # Start extrude factor update timer
        self.reactor.update_timer(self.extrude_factor_update_timer,
                                  self.reactor.NOW)

    def update_filament_array(self, last_epos):
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

    def extrude_factor_update_event(self, eventtime):
        # Update extrude factor
        pos = self.toolhead.get_position()
        last_epos = pos[3]
        # Update filament array for lastFilamentWidthReading
        if self.sensor.use_internal_delay:
            self.sensor.update_internal_arrais(last_epos)
        self.update_filament_array(last_epos)
        # Check runout

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
                    percentage = round(self.nominal_filament_dia**2
                                       / self.filament_width**2 * 100)
                    self.gcode.run_script("M221 S" + str(percentage))
                else:
                    self.gcode.run_script("M221 S100")
        else:
            self.gcode.run_script("M221 S100")
            self.filament_array = []

        if self.is_active:
            return eventtime + 1
        else:
            return self.reactor.NEVER

    def cmd_M407(self, gcmd):
        gcmd.respond_info(str(self.sensor))

    def cmd_ClearFilamentArray(self, gcmd):
        self.filament_array = []
        gcmd.respond_info("Filament width measurements cleared!")
        # Set extrude multiplier to 100%
        self.gcode.run_script_from_command("M221 S100")

    def cmd_M405(self, gcmd):
        response = "Filament width sensor Turned On"
        if self.is_active:
            response = "Filament width sensor is already On"
        else:
            self.is_active = True
            # Start extrude factor update timer
            self.reactor.update_timer(self.extrude_factor_update_timer,
                                      self.reactor.NOW)
        gcmd.respond_info(response)

    def cmd_M406(self, gcmd):
        response = "Filament width sensor Turned Off"
        if not self.is_active:
            response = "Filament width sensor is already Off"
        else:
            self.is_active = False
            # Stop extrude factor update timer
            self.reactor.update_timer(self.extrude_factor_update_timer,
                                      self.reactor.NEVER)
            # Clear filament array
            self.filament_array = []
            # Set extrude multiplier to 100%
            self.gcode.run_script_from_command("M221 S100")
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
