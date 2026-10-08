# Журнал архитектурного рефакторинга (Clean Architecture)

**Этап 1: Внедрение слоя аппаратных абстракций (HAL) и разделение роутов**

## Что было сделано:
1. **Резервная копия:** Перед началом работ был создан Git-тег ackup-pre-arch-refactor, фиксирующий стабильное состояние (с 
umexpr и ThreadPoolExecutor).
2. **Слой HAL (hardware/hal.py):** 
   - Вынесены интерфейсы ClimateSensor и SoilSensor.
   - Созданы аппаратные реализации (RealSHT30, RealADS1115), использующие smbus2 и защитный i2c_executor.
   - Созданы программные Mock-реализации (MockSHT30, MockADS1115) для локальной разработки.
   - Механизм Dependency Injection динамически определяет IS_EDGE_DEVICE и отдает нужный инстанс.
3. **Разделение роутов (pi/routes/downloads.py):**
   - Роуты скачивания архивов (/download/csv, /download/images_zip) успешно перенесены в отдельный APIRouter.
   - Подключена инициализация путей DATA_DIR и STATIC_DIR через функцию init_downloads.
4. **Интеграция в web_station.py:**
   - Монолит теперь использует get_climate_sensor() и get_soil_sensor() вместо  грязного прямого опроса I2C.
   - Файл web_station.py стал легче (удален кусок кода со скачиваниями, подключен роутер downloads_router).

## Инструкция по восстановлению (Rollback)
В случае, если новые абстракции сломали пайплайн или I2C перестал отвечать:
1. Подключитесь по SSH к Orange Pi.
2. Перейдите в папку проекта: cd /home/pi/plant-stress-ndvi
3. Откатите изменения к сохраненному тегу:
   git reset --hard backup-pre-arch-refactor
4. Перезапустите службу веб-сервера.

**Этап 2: Relay HAL + Pydantic Config и Pandas Chunking**

1. Создан core/config.py с Pydantic BaseSettings.
2. В hardware/hal.py добавлены абстракции RelayController, RealGPIODRelay и MockRelay.
3. Модуль src/relay_controller.py теперь является тонкой оберткой над HAL.
4. Хардкод пинов удален из бизнес-логики.
5. В src/statistical_analysis.py внедрена загрузка через chunksize для экономии памяти.
