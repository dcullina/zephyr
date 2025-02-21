# Copyright (c) 2024 Chen Xingyu <hi@xingrz.me>
# SPDX-License-Identifier: Apache-2.0

'''Runner for probe-rs.'''

import os
import shlex

from runners.core import FileType, RunnerCaps, ZephyrBinaryRunner
from west import log


class ProbeRsBinaryRunner(ZephyrBinaryRunner):
    '''Runner front-end for probe-rs.'''

    def __init__(self, cfg, chip,
                 probe_rs='probe-rs',
                 dev_id=None,
                 dt_flash=True,
                 erase=False,
                 reset=False,
                 protocol='swd',
                 speed=None,
                 tool_opt=None):
        super().__init__(cfg)
        self.chip = chip
        self.probe_rs = probe_rs
        self.dev_id = dev_id
        self.dt_flash = dt_flash
        self.erase = erase
        self.reset = reset
        self.elf_name = cfg.elf_file
        self.bin_name = cfg.bin_file
        self.hex_name = cfg.hex_file
        self.file = cfg.file
        self.file_type = cfg.file_type
        self.protocol = protocol
        self.speed = speed

        self.tool_opt = []
        if tool_opt is not None:
            for opts in [shlex.split(opt) for opt in tool_opt]:
                self.tool_opt += opts


    @classmethod
    def name(cls):
        return 'probe-rs'

    @classmethod
    def capabilities(cls):
        return RunnerCaps(
            commands={'flash'},
            dev_id=True,
            erase=True,
            reset=True,
            flash_addr=True,
            file=True,
            hide_load_files=True,
            tool_opt=True,
            rtt=False
        )

    @classmethod
    def do_add_parser(cls, parser):
        # Required:
        parser.add_argument(
            '--chip',
            required=True,
            help='chip name'
        )

        # Optional:
        parser.add_argument(
            '--probe-rs',
            required=False,
            default='probe-rs',
            help='path to probe-rs tool, default is probe-rs'
        )
        parser.add_argument(
            '--protocol',
            required=False,
            default='swd',
            help='protocol used (swd/jtag), default is swd'
        )
        parser.add_argument(
            '--speed',
            required=False,
            default=None,
            help='the protocol speed in kHz'
        )

        parser.set_defaults(reset=False)
        parser.set_defaults(dt_flash=True)

    @classmethod
    def dev_id_help(cls) -> str:
        return '''select a specific probe, in the form `VID:PID:<Serial>`'''

    @classmethod
    def tool_opt_help(cls) -> str:
        return '''additional options for probe-rs,
                  e.g. --chip-description-path=/path/to/chip.yml'''

    @classmethod
    def do_create(cls, cfg, args):
        return ProbeRsBinaryRunner(cfg, args.chip,
                                   probe_rs=args.probe_rs,
                                   dev_id=args.dev_id,
                                   dt_flash=args.dt_flash,
                                   erase=args.erase,
                                   reset=args.reset,
                                   protocol=args.protocol,
                                   tool_opt=args.tool_opt)

    def do_run(self, command, **kwargs):
        self.require(self.probe_rs)

        probe_config_args = ['--chip', self.chip]
        if self.dev_id is not None:
            probe_config_args += ['--probe', self.dev_id]
        if self.protocol:
            probe_config_args += ['--protocol', self.protocol]
        if self.speed:
            probe_config_args += ['--speed', self.speed]

        if command == 'flash':
            self.do_flash(probe_config_args, **kwargs)

    def do_flash(self, probe_config_args, **kwargs):
        download_args = ['--connect-under-reset']

        if self.erase:
            download_args += ['--chip-erase']

        if self.file is not None:
            if not os.path.isfile(self.file):
                err = 'Cannot flash; file ({}) not found'
                raise ValueError(err.format(self.file))

            download_args += [self.file]

            if self.file_type == FileType.ELF:
                download_args += [
                    "--binary-format",
                    "elf"
                ]
            elif self.file_type == FileType.HEX:
                download_args += [
                    "--binary-format",
                    "hex"
                ]
            elif self.file_type == FileType.BIN:
                download_args += [
                    "--binary-format",
                    "bin",
                    "--base-address",
                ]
                if self.dt_flash:
                    download_args += [
                        f"0x{self.flash_address_from_build_conf(self.build_conf):x}"
                    ]
                else:
                    download_args += [
                        "0"
                    ]

            else:
                log.wrn("West could not detect a filetype, attempting to flash anyways...")

        else:
            if self.elf_name is not None and os.path.isfile(self.elf_name):
                download_args += [
                    "--binary-format",
                    "elf",
                    self.elf_name
                ]
            elif self.hex_name is not None and os.path.isfile(self.hex_name):
                download_args += [
                    "--binary-format",
                    "hex",
                    self.hex_name
                ]
            elif self.bin_name is not None and os.path.isfile(self.bin_name):
                download_args += [
                    "--binary-format",
                    "bin",
                    self.bin_name,
                    "--base-address"
                ]
                if self.dt_flash:
                    download_args += [
                        f"0x{self.flash_address_from_build_conf(self.build_conf):x}"
                    ]
                else:
                    download_args += [
                        "0"
                    ]
            else:
                err = "Cannot flash; no elf ({}), hex ({}), or bin ({}) files found."
                raise ValueError(err.format(self.elf_name, self.hex_name, self.bin_name))

        self.check_call([self.probe_rs, 'download'] +
                        download_args + probe_config_args)

        if self.reset:
            self.check_call([self.probe_rs, 'reset']
                        + probe_config_args)
