"""
Unit tests for VisionOps (PIL, pyautogui, and LLM calls fully mocked)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, PropertyMock

from zenus_core.tools.vision_ops import VisionOps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vision():
    """Return a VisionOps instance with lazy-loaded deps pre-injected"""
    v = VisionOps()
    return v


def _mock_screenshot_image():
    """Build a minimal PIL Image mock that supports save()"""
    img = Mock()
    img.save = Mock()
    return img


# ---------------------------------------------------------------------------
# Lazy-load properties
# ---------------------------------------------------------------------------

class TestVisionOpsLazyLoad:
    """Tests for lazy-loading of PIL and pyautogui"""

    def test_pil_image_available(self):
        """PIL_Image property returns the Image module when PIL is installed"""
        v = VisionOps()
        with patch.dict("sys.modules", {"PIL": MagicMock(), "PIL.Image": MagicMock()}):
            v._pil_image = None  # force reload
            from PIL import Image
            v._pil_image = Image
            assert v.PIL_Image is Image

    def test_pil_image_raises_when_unavailable(self):
        """PIL_Image raises RuntimeError when PIL import fails"""
        v = VisionOps()
        v._pil_image = None
        with patch("builtins.__import__", side_effect=ImportError("no PIL")):
            with pytest.raises((RuntimeError, ImportError)):
                _ = v.PIL_Image

    def test_pil_imagegrab_available(self):
        """PIL_ImageGrab property returns ImageGrab when PIL is installed"""
        v = VisionOps()
        mock_grab = MagicMock()
        v._pil_imagegrab = mock_grab
        assert v.PIL_ImageGrab is mock_grab

    def test_pyautogui_raises_when_unavailable(self):
        """pyautogui property raises RuntimeError when not installed"""
        v = VisionOps()
        v._pyautogui = None
        with patch("builtins.__import__", side_effect=ImportError("no pyautogui")):
            with pytest.raises((RuntimeError, ImportError)):
                _ = v.pyautogui


# ---------------------------------------------------------------------------
# screenshot
# ---------------------------------------------------------------------------

class TestVisionOpsScreenshot:
    """Tests for VisionOps.screenshot"""

    def _make_tool_with_pyautogui(self, mock_pyautogui):
        v = VisionOps()
        v._pyautogui = mock_pyautogui
        return v

    def test_screenshot_full_screen_returns_temp_path(self):
        """Full screenshot is saved to /tmp and path returned"""
        mock_pag = Mock()
        img = _mock_screenshot_image()
        mock_pag.screenshot.return_value = img
        v = self._make_tool_with_pyautogui(mock_pag)
        result = v.screenshot()
        assert "/tmp/" in result
        img.save.assert_called()

    def test_screenshot_with_save_path_returns_that_path(self):
        """Screenshot with save_path returns the provided path"""
        mock_pag = Mock()
        img = _mock_screenshot_image()
        mock_pag.screenshot.return_value = img
        v = self._make_tool_with_pyautogui(mock_pag)
        result = v.screenshot(save_path="/tmp/myshot.png")
        assert "/tmp/myshot.png" in result

    def test_screenshot_with_region(self):
        """Region argument is passed to pyautogui.screenshot"""
        mock_pag = Mock()
        img = _mock_screenshot_image()
        mock_pag.screenshot.return_value = img
        v = self._make_tool_with_pyautogui(mock_pag)
        v.screenshot(region=(0, 0, 800, 600))
        mock_pag.screenshot.assert_called_with(region=(0, 0, 800, 600))

    def test_screenshot_stores_last_screenshot(self):
        """screenshot stores result in self.last_screenshot"""
        mock_pag = Mock()
        img = _mock_screenshot_image()
        mock_pag.screenshot.return_value = img
        v = self._make_tool_with_pyautogui(mock_pag)
        v.screenshot()
        assert v.last_screenshot is img

    def test_screenshot_exception_returns_error(self):
        """Exception during screenshot returns 'Screenshot failed: ...'"""
        mock_pag = Mock()
        mock_pag.screenshot.side_effect = Exception("display unavailable")
        v = self._make_tool_with_pyautogui(mock_pag)
        result = v.screenshot()
        assert "Screenshot failed" in result
        assert "display unavailable" in result


# ---------------------------------------------------------------------------
# analyze_screenshot
# ---------------------------------------------------------------------------

class TestVisionOpsAnalyzeScreenshot:
    """Tests for VisionOps.analyze_screenshot"""

    def test_returns_error_when_no_screenshot_and_no_path(self):
        """Returns message when no screenshot is available"""
        v = VisionOps()
        v.last_screenshot = None
        result = v.analyze_screenshot("What is on screen?")
        assert "No screenshot" in result

    def test_loads_image_from_path(self):
        """Loads image from screenshot_path when provided"""
        v = VisionOps()
        mock_image_module = Mock()
        mock_img = _mock_screenshot_image()
        # mock save so BytesIO gets something
        mock_img.save = Mock()
        mock_image_module.open.return_value = mock_img
        v._pil_image = mock_image_module

        mock_llm = Mock()
        mock_llm.analyze_image.return_value = "A desktop"

        with patch("zenus_core.brain.llm.factory.get_llm", return_value=mock_llm):
            result = v.analyze_screenshot("Describe", screenshot_path="/tmp/test.png")
        mock_image_module.open.assert_called_with("/tmp/test.png")

    def test_uses_last_screenshot_when_no_path(self):
        """Uses last_screenshot when no path is provided"""
        v = VisionOps()
        mock_img = Mock()
        mock_img.save = Mock()
        v.last_screenshot = mock_img

        mock_llm = Mock()
        mock_llm.analyze_image.return_value = "Screen content"

        with patch("zenus_core.brain.llm.factory.get_llm", return_value=mock_llm):
            result = v.analyze_screenshot("Describe")
        assert result == "Screen content"

    def test_returns_error_when_image_file_not_found(self):
        """Returns 'Failed to load image' when PIL.open raises"""
        v = VisionOps()
        mock_image_module = Mock()
        mock_image_module.open.side_effect = Exception("file not found")
        v._pil_image = mock_image_module

        result = v.analyze_screenshot("Describe", screenshot_path="/tmp/missing.png")
        assert "Failed to load image" in result

    def test_llm_without_analyze_image_returns_message(self):
        """LLM without analyze_image method returns unsupported message"""
        v = VisionOps()
        mock_img = Mock()
        mock_img.save = Mock()
        v.last_screenshot = mock_img

        mock_llm = Mock(spec=[])  # spec=[] means no attributes

        with patch("zenus_core.brain.llm.factory.get_llm", return_value=mock_llm):
            result = v.analyze_screenshot("Describe")
        assert "doesn't support vision" in result or "not support" in result.lower() or "Current LLM" in result

    def test_llm_exception_returns_error(self):
        """Exception from LLM returns 'Vision analysis failed'"""
        v = VisionOps()
        mock_img = Mock()
        mock_img.save = Mock()
        v.last_screenshot = mock_img

        with patch("zenus_core.brain.llm.factory.get_llm", side_effect=Exception("api error")):
            result = v.analyze_screenshot("Describe")
        assert "Vision analysis failed" in result


# ---------------------------------------------------------------------------
# find_on_screen
# ---------------------------------------------------------------------------

class TestVisionOpsFindOnScreen:
    """Tests for VisionOps.find_on_screen"""

    def test_takes_screenshot_when_none_exists(self):
        """find_on_screen captures screenshot first if last_screenshot is None"""
        v = VisionOps()
        v.last_screenshot = None
        v.screenshot = Mock(return_value="Screenshot captured: /tmp/x.png")
        v.analyze_screenshot = Mock(return_value="Found at (100, 200)")

        result = v.find_on_screen("the login button")
        v.screenshot.assert_called_once()

    def test_uses_existing_screenshot(self):
        """find_on_screen skips screenshot if last_screenshot exists"""
        v = VisionOps()
        v.last_screenshot = Mock()
        v.screenshot = Mock()
        v.analyze_screenshot = Mock(return_value="Found at (50, 50)")

        v.find_on_screen("search box")
        v.screenshot.assert_not_called()

    def test_returns_analyze_result(self):
        """find_on_screen returns result from analyze_screenshot"""
        v = VisionOps()
        v.last_screenshot = Mock()
        v.analyze_screenshot = Mock(return_value="Coordinates: (120, 340)")

        result = v.find_on_screen("submit button")
        assert "120" in result or "Coordinates" in result


# ---------------------------------------------------------------------------
# click / double_click / right_click / move_to / drag
# ---------------------------------------------------------------------------

class TestVisionOpsMouseOps:
    """Tests for VisionOps mouse operations"""

    def _make_tool(self):
        v = VisionOps()
        v._pyautogui = Mock()
        return v

    def test_click_at_coordinates(self):
        """click with x,y calls pyautogui.click"""
        v = self._make_tool()
        result = v.click(x=100, y=200)
        v._pyautogui.click.assert_called_with(100, 200)
        assert "Clicked at (100, 200)" in result

    def test_click_without_args_returns_message(self):
        """click without coordinates or description returns guidance"""
        v = self._make_tool()
        result = v.click()
        assert "Provide" in result or "coordinate" in result.lower()

    def test_click_exception_returns_error(self):
        """Exception during click returns 'Click failed'"""
        v = self._make_tool()
        v._pyautogui.click.side_effect = Exception("no display")
        result = v.click(x=10, y=20)
        assert "Click failed" in result

    def test_click_with_description_calls_find(self):
        """click with description calls find_on_screen first"""
        v = self._make_tool()
        v.find_on_screen = Mock(return_value="Found at (50, 60)")
        result = v.click(description="the submit button")
        v.find_on_screen.assert_called_once()
        assert "Found" in result

    def test_double_click_calls_pyautogui(self):
        """double_click calls pyautogui.doubleClick"""
        v = self._make_tool()
        result = v.double_click(50, 75)
        v._pyautogui.doubleClick.assert_called_with(50, 75)
        assert "Double-clicked" in result

    def test_double_click_exception_returns_error(self):
        """Exception during double_click returns 'Double-click failed'"""
        v = self._make_tool()
        v._pyautogui.doubleClick.side_effect = Exception("fail")
        result = v.double_click(10, 20)
        assert "Double-click failed" in result

    def test_right_click_calls_pyautogui(self):
        """right_click calls pyautogui.rightClick"""
        v = self._make_tool()
        result = v.right_click(30, 40)
        v._pyautogui.rightClick.assert_called_with(30, 40)
        assert "Right-clicked" in result

    def test_right_click_exception_returns_error(self):
        """Exception during right_click returns 'Right-click failed'"""
        v = self._make_tool()
        v._pyautogui.rightClick.side_effect = Exception("fail")
        result = v.right_click(10, 10)
        assert "Right-click failed" in result

    def test_move_to_calls_pyautogui(self):
        """move_to calls pyautogui.moveTo"""
        v = self._make_tool()
        result = v.move_to(100, 200)
        v._pyautogui.moveTo.assert_called()
        assert "Moved to (100, 200)" in result

    def test_move_to_exception_returns_error(self):
        """Exception during move_to returns 'Move failed'"""
        v = self._make_tool()
        v._pyautogui.moveTo.side_effect = Exception("fail")
        result = v.move_to(0, 0)
        assert "Move failed" in result

    def test_drag_calls_moveto_and_drag(self):
        """drag calls pyautogui.moveTo then drag"""
        v = self._make_tool()
        result = v.drag(0, 0, 100, 100)
        v._pyautogui.moveTo.assert_called_with(0, 0)
        v._pyautogui.drag.assert_called()
        assert "Dragged" in result

    def test_drag_exception_returns_error(self):
        """Exception during drag returns 'Drag failed'"""
        v = self._make_tool()
        v._pyautogui.moveTo.side_effect = Exception("fail")
        result = v.drag(0, 0, 10, 10)
        assert "Drag failed" in result


# ---------------------------------------------------------------------------
# type_text / press_key / hotkey
# ---------------------------------------------------------------------------

class TestVisionOpsKeyboardOps:
    """Tests for VisionOps keyboard operations"""

    def _make_tool(self):
        v = VisionOps()
        v._pyautogui = Mock()
        return v

    def test_type_text_calls_write(self):
        """type_text calls pyautogui.write with text and interval"""
        v = self._make_tool()
        result = v.type_text("Hello world")
        v._pyautogui.write.assert_called_with("Hello world", interval=0.05)
        assert "Typed" in result

    def test_type_text_exception_returns_error(self):
        """Exception during type_text returns 'Type failed'"""
        v = self._make_tool()
        v._pyautogui.write.side_effect = Exception("fail")
        result = v.type_text("test")
        assert "Type failed" in result

    def test_press_key_calls_pyautogui(self):
        """press_key calls pyautogui.press"""
        v = self._make_tool()
        result = v.press_key("enter")
        v._pyautogui.press.assert_called_with("enter")
        assert "enter" in result

    def test_press_key_exception_returns_error(self):
        """Exception during press_key returns 'Key press failed'"""
        v = self._make_tool()
        v._pyautogui.press.side_effect = Exception("fail")
        result = v.press_key("esc")
        assert "Key press failed" in result

    def test_hotkey_calls_pyautogui(self):
        """hotkey calls pyautogui.hotkey"""
        v = self._make_tool()
        result = v.hotkey("ctrl", "c")
        v._pyautogui.hotkey.assert_called_with("ctrl", "c")
        assert "ctrl+c" in result

    def test_hotkey_exception_returns_error(self):
        """Exception during hotkey returns 'Hotkey failed'"""
        v = self._make_tool()
        v._pyautogui.hotkey.side_effect = Exception("fail")
        result = v.hotkey("ctrl", "z")
        assert "Hotkey failed" in result


# ---------------------------------------------------------------------------
# get_screen_text / fill_form
# ---------------------------------------------------------------------------

class TestVisionOpsAdvanced:
    """Tests for get_screen_text and fill_form"""

    def test_get_screen_text_calls_analyze(self):
        """get_screen_text delegates to analyze_screenshot"""
        v = VisionOps()
        v.last_screenshot = Mock()
        v.analyze_screenshot = Mock(return_value="Some text on screen")
        result = v.get_screen_text()
        v.analyze_screenshot.assert_called_once()
        assert "Some text on screen" in result

    def test_get_screen_text_takes_screenshot_when_none(self):
        """get_screen_text captures screenshot if last_screenshot is None"""
        v = VisionOps()
        v.last_screenshot = None
        v.screenshot = Mock(side_effect=lambda: setattr(v, "last_screenshot", Mock()) or "captured")
        v.analyze_screenshot = Mock(return_value="Text")
        v.get_screen_text()
        v.screenshot.assert_called_once()

    def test_fill_form_iterates_fields(self):
        """fill_form calls find_on_screen for each field"""
        v = VisionOps()
        v.find_on_screen = Mock(return_value="Found at (10, 20)")
        result = v.fill_form({"Name": "Alice", "Email": "alice@example.com"})
        assert v.find_on_screen.call_count == 2
        assert "Name" in result
        assert "Email" in result


# ---------------------------------------------------------------------------
# wait_for_element
# ---------------------------------------------------------------------------

class TestVisionOpsWaitForElement:
    """Tests for VisionOps.wait_for_element"""

    def test_returns_immediately_when_found(self):
        """Returns 'Element appeared' as soon as find_on_screen indicates found"""
        v = VisionOps()
        v.screenshot = Mock()
        v.find_on_screen = Mock(return_value="Element found at (50, 50)")
        result = v.wait_for_element("login button", timeout=5)
        assert "appeared" in result.lower() or "found" in result.lower()

    def test_returns_timeout_message_when_not_found(self):
        """Returns 'Timeout waiting for' when element never appears"""
        v = VisionOps()
        v.screenshot = Mock()
        v.find_on_screen = Mock(return_value="Not visible anywhere")

        with patch("time.time", side_effect=[0, 999]):
            with patch("time.sleep"):
                result = v.wait_for_element("ghost button", timeout=1)
        assert "Timeout" in result
