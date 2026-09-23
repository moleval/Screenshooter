# ТЗ: Маркеры манипуляций для аннотаций

## Цель

Добавить визуальные маркеры изменения размера для всех обычных аннотаций (линии, стрелки, прямоугольники, эллипсы, текст) без нарушения существующего поведения. Поворот не входит.

## Архитектурные правила

1. AnnotationResizeController — единственный владелец логики resize через маркеры.
2. MouseInteractionManager — чистый диспетчер; один вызов контроллера в цепочке.
3. CropHandles — низкоуровневый механизм отображения/хит-теста произвольных маркеров (не знает об аннотациях).
4. Undo/Redo — команда ResizeAnnotationCommand вводится с этапа прямоугольника и используется для всех типов.
5. Изменение геометрии — только через нативные методы (setRect, setLine, set_points, set_curve), не через setPos/setScale (кроме текста).
6. Ограничения: MIN_RECT_SIZE=5 для фигур, MIN_ARROW_LENGTH для линий/стрелок, MIN_SCALE=0.1 для текста.
7. Ограничение фона — применяется ко всем, кроме текста.
8. Текст — 4 угловых маркера, setScale (временно), учёт поворота через mapToScene.

## Порядок dispatch

blur → crop → blur_outside → annotation_resize → manipulation → text → drawing

annotation_resize строго после blur_outside, но до manipulation, иначе клик по маркеру станет перетаскиванием.

Defense in depth: контроллер возвращает False, если активен blur_mode или crop_mode.

## Модель маркеров по типам

| Тип | Режимы | Маркеров | Расположение | Манипуляции |
|-----|--------|----------|--------------|-------------|
| Линия (LineItem, WavyLineItem) | straight, dashed, wavy | 2 | start, end | Длина/направление |
| Стрелка прямая (ArrowItem, DimensionItem) | straight, dimension | 2 | start, end | Длина/направление |
| Кривая стрелка (CurvedArrowItem) | curved | 3 | start, end, ctrl | Крайние — концы, ctrl — изгиб |
| Прямоугольник (RectangleItem) | rect, square | 8 | 4 угла + 4 середины | Углы — от противоположного, середины — по оси |
| Эллипс (EllipseItem) | ellipse, circle | 2 | правый, верхний | Правый — горизонтальный радиус, верхний — вертикальный |
| Заливка (FilledRectItem) | filled | 8 | как прямоугольник | как прямоугольник |
| Облако (CloudItem) | cloud | 8 | как прямоугольник | как прямоугольник + build_path |
| Текст (TextItem) | — | 4 | 4 угла | Пропорциональное масштабирование с фиксацией противоположного угла |

### Уточнения модели

- Средний маркер линий/стрелок исключён из текущего этапа.
- DimensionItem не поглощается ArrowItem — остаётся отдельным типом.
- Эллипс имеет 2 маркера, не 3.
- Тип элемента при resize не меняется.

## Этапы реализации

### Шаг 0. Подготовка

- Проверить тесты.
- Создать ветку feature/annotation-handles.
- Зафиксировать baseline.
- Записать baseline и результаты регрессии в REGRESSION_NOTES.md.

### Этап 1. Обобщение CropHandles + цвет темы

- API create_handles(points: dict).
- Legacy-обёртка для rect.
- Новый ключ темы annotation_handle для светлой/тёмной темы.
- Unit-тесты.

### Этап 2. Скелет AnnotationResizeController + dispatch

- Создать контроллер; методы на начальном этапе возвращают False.
- Интегрировать в EditorView и MouseInteractionManager.
- Приоритет: после blur_outside, до manipulation.
- Добавить тест порядка вызовов.

### Этап 3. Прямоугольник + ResizeAnnotationCommand

- RectangleItem: get_handle_points(), set_handle_geometry(), get/set_geometry_state().
- Полный цикл controller: press → move → release.
- Создать ResizeAnnotationCommand.
- Ограничение фона в контроллере (_clamp_to_background).
- Синхронизация в EditorView._do_selection_update().

### Этап 4. Остальные фигуры

- EllipseItem: 2 маркера.
- FilledRectItem, CloudItem: 8 маркеров; для облака вызывать build_path.

### Этап 5. Линии и прямые стрелки

- LineItem, WavyLineItem, ArrowItem, DimensionItem.
- 2 маркера: start, end.
- Использовать нативные методы изменения геометрии.
- Средний маркер не добавлять.

### Этап 6. Кривая стрелка

- CurvedArrowItem: 3 маркера — start, end, ctrl.
- Изменение кривой через set_curve.

### Этап 7. Текст

- 4 угловых маркера.
- get_handle_points() через mapToScene(rect.corner) с учётом поворота.
- Масштабирование через setScale с фиксацией противоположного угла.
- Маркеры скрыты при _editable == True.
- Добавить тест с setRotation(45).

### Этап 8. Унификация Undo/Redo

- Проверить ResizeAnnotationCommand для всех типов.
- Один drag = одна запись истории.

### Этап 9. Видимость, режимы, экспорт

- Централизованное обновление в _do_selection_update().
- Скрытие при множественном выделении, crop/blur, смене инструмента и редактировании текста.
- Exporter.render_scene_to_image(): скрытие/показ handles через try/finally.

### Этап 10. Полная регрессия

- Все тесты.
- Ручные сценарии.
- Оптимизация: обновлять позиции существующих маркеров, не пересоздавать их без необходимости.

## Критерии готовности

- Маркеры появляются при одиночном выделении всех типов.
- Перетаскивание маркеров изменяет геометрию/масштаб.
- Маркеры не показываются при множественном выделении и в crop/blur.
- Handle не перехватывает обычное перемещение.
- Handle неактивен в crop/blur даже при случайном наличии в сцене.
- Undo/Redo атомарно для всех типов.
- Маркеры не попадают в экспорт; visibility восстанавливается даже при ошибке через try/finally.
- Ограничение фона применяется ко всем, кроме текста.
- Минимальные размеры соблюдаются.
- Resize не меняет тип аннотации.
- Существующее поведение не нарушено.
- Автотесты проходят.

## Что не входит

- Поворот аннотаций.
- Средний маркер линий/стрелок: изгиб и переключение straight↔curved.
- Расширение атрибутов текста: выравнивание, жирность, курсив и т. п.
- Переименование CropHandles → AnnotationHandles (технический долг).
- Изменение логики crop/blur/pasted image handles.

## Планируемые файлы

### Новые

- screenshooter/controllers/annotation_resize_controller.py
- test_crop_handles_custom_points.py
- test_annotation_resize_controller_dispatch.py
- test_annotation_handles_*.py
- test_annotation_resize_undo_redo_all.py
- test_annotation_handles_visibility_export.py

### Изменяемые

- screenshooter/items/crop_handles.py
- screenshooter/items/shape_items.py
- screenshooter/items/line_items.py
- screenshooter/items/arrow_items.py
- screenshooter/items/text_item.py
- screenshooter/controllers/mouse_interaction_manager.py
- screenshooter/controllers/manipulation_controller.py (возможно, минимально)
- screenshooter/history/item_commands.py
- screenshooter/view.py
- screenshooter/export.py
- screenshooter/theme.py
