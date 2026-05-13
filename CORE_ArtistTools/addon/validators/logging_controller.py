# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import logging
import os


class PrintHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        print(log_entry)


logger = logging.getLogger("validation")
logger.setLevel(logging.DEBUG)

# Change the log file path to the user's home directory
log_file_path = os.path.join(os.path.expanduser("~"), "validation.log")
file_handler = logging.FileHandler(log_file_path)
console_handler = logging.StreamHandler()
print_handler = PrintHandler()

console_handler.setLevel(logging.INFO)
file_handler.setLevel(logging.DEBUG)
print_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)
print_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)
logger.addHandler(print_handler)
