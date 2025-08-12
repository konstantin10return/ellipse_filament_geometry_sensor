Модуль для Klipper. Позволяет добавить поддержку датчика геометрии филамента, учитывающего овальность.

```
[hall_ellipse_filament_geometry_sensor_2]
measurement_delay:
# measurement_interval: 5
# use_current_dia_while_delay: False
# default_nominal_filament_diameter:
# max_difference: 5
# min_diameter:
# max_diameter:
# logging: False

s1_adc1_pin:
s1_adc2_pin:
s2_adc1_pin:
s2_adc2_pin:
s3_adc1_pin:
s3_adc2_pin:

# s1_Cal_dia1: 1.5
# s1_Cal_dia2: 2.0
# s2_Cal_dia1: 1.5
# s2_Cal_dia2: 2.0
# s3_Cal_dia1: 1.5
# s3_Cal_dia2: 2.0

# s1_Raw_dia1: 9500
# s1_Raw_dia2: 10500
# s2_Raw_dia1: 9500
# s2_Raw_dia2: 10500
# s3_Raw_dia1: 9500
# s3_Raw_dia2: 10500


# use_internal_delay: False
# Нужно ли использовать внутренние FIFO массивы для учета расстояния между модулями
# internel_delay: 14.6
# Расстояние между модулями

# precision: 100
# Точность вычисления большей полуоси. Значение 100 даст погрешность вычислений +-0.01.
# Значение 10 даст погрешность вычислений +-0.1. Чем больше значение этого параметра,
# тем выше нагрузка на хост.

# check_e_pos_timeout: 1
# Период проверки окончания филамента положения экструдера
# binding_of_measurement: extruder_stepper
# Откуда брать координату для привязки значения измерения
# 'extruder_stepper' или 'toolhead'
# extruder_stepper будет точнее чем 'toolhead'

# ----------- Настройки E move cuter ----------- !
# use_e_move_cuter: False
# Использовать ли E move cuter
# max_e_move_len: 10
# Максимальная длина микродвижения
```
