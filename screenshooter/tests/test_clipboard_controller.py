class FakeViewport:
    def update(self):
        pass


class FakeView:
    def __init__(self):
        self._scene = QGraphicsScene()
        self.pasted_images = []
        self.blur_controller = FakeBlurController()
        self.history = FakeHistory()
        self._background_item = None
        self._viewport = FakeViewport()

    def scene(self):
        return self._scene

    def viewport(self):
        return self._viewport

    def _is_background_item(self, item):
        return item is self._background_item

    def _item_for_manipulation(self, item):
        return item

    def _update_pasted_image_handles(self):
        pass

    def _invalidate_cursor_cache(self):
        pass

    def _update_blur_region_handles(self):
        pass

    def show_status_message(self, *args, **kwargs):
        pass