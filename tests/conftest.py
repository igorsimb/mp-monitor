# def pytest_addoption(parser):
#     parser.addoption("--show-capture", action="store_true", default=True, help="Show capture output for all tests")
#
# def pytest_configure(config):
#     if not config.option.show_capture:
#         terminal = config.pluginmanager.getplugin("terminal")
#         if terminal:
#             terminal.TerminalReporter.showcapture = "no"
