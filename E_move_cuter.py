# next_transform closer to toolhead
# last_transform closer to gcode_move


class EMoveCuter:
    def __init__(self, config, loging=True):
        self.max_move_len = config.getfloat("max_e_move_len", 10, minval=0.01)
        self.in_move_callback = self.in_move_callback
        self.loging = loging
        self.next_transform = None
        self.extrude_factor = 1
        self.printer = config.get_printer()
        self.printer.register_event_handler("klippy:connect", self._handle_connect)
        self.gcode = self.printer.lookup_object('gcode')
        self.last_transform_e_pos, self.next_transform_e_pos = 0, 0

    def _handle_connect(self):
        gcode_move = self.printer.lookup_object('gcode_move')
        self.next_transform = gcode_move.set_move_transform(self, force=True)
        self.last_transform_e_pos = self.next_transform_e_pos = self.next_transform.get_position()[3]

    def in_move_callback(self):
        if self.loging:
            self.gcode.respond_info("EMoveCuter \n    in_move_callback is not defined !!!")

    def set_extrude_factor(self, extrude_factor):
        self.extrude_factor = extrude_factor
        if self.loging:
            self.gcode.respond_info(f"EMoveCuter \n    extrude_factor={extrude_factor}")

    def set_in_move_callback(self, new_callback):
        self.in_move_callback = new_callback
        if self.loging:
            self.gcode.respond_info("EMoveCuter \n    in_move_callback defined")

    def get_position(self):
        return self.next_transform.get_position()[0:3] + [self.last_transform_e_pos]

    def move(self, newpos, speed):  # motion split function
        if (newpos[3] - self.last_transform_e_pos) * self.extrude_factor <= self.max_move_len:
            next_transform_newpos = list(newpos).copy()
            next_transform_newpos[3] = self.next_transform_e_pos + ((newpos[3] - self.last_transform_e_pos) * self.extrude_factor)
            self.next_transform.move(next_transform_newpos, speed)
            self.last_transform_e_pos = newpos[3]
            self.next_transform_e_pos = next_transform_newpos[3]
            self.in_move_callback()
            return None

        start_pos = tuple(self.next_transform.get_position())
        next_transform_pos = list(start_pos)
        remaining_d = [newpos[i] - start_pos[i] for i in range(3)]
        remaining_d.append(newpos[3] - self.last_transform_e_pos)
        while remaining_d[3] * self.extrude_factor > self.max_move_len:
            last_transform_e_pos_change = self.max_move_len / self.extrude_factor
            fraction = last_transform_e_pos_change / remaining_d[3]
            last_transform_xyz_pos_change = [remaining_d[i] * fraction for i in range(3)]
            for axis_n in range(3):
                remaining_d[axis_n] -= last_transform_xyz_pos_change[axis_n]
                next_transform_pos[axis_n] += last_transform_xyz_pos_change[axis_n]
            remaining_d[3] -= last_transform_e_pos_change
            self.last_transform_e_pos += last_transform_e_pos_change
            next_transform_pos[3] += self.max_move_len
            self.next_transform.move(next_transform_pos, speed)
            self.in_move_callback()
        next_transform_pos[0:3] = newpos[0:3]
        next_transform_pos[3] += remaining_d[3] * self.extrude_factor
        self.next_transform_e_pos = next_transform_pos[3]
        self.next_transform.move(next_transform_pos[:4], speed)
        self.in_move_callback()
