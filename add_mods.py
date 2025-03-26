#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import sys
import pathlib
import subprocess
from datetime import datetime
import time

def print_step(message):
    """打印当前步骤信息"""
    print(f"\n=== {message} ===")

def get_mod_name(filename):
    """从文件名提取mod名称"""
    if filename.endswith('.pw.toml'):
        return filename[:-8]  # 移除.pw.toml后缀
    elif filename.endswith('.jar'):
        return filename[:-4]  # 移除.jar后缀
    return filename

def scan_mods(mods_dir):
    """扫描mods目录，返回包含所有mod名称的列表"""
    mod_names = []
    print_step(f"正在扫描目录: {mods_dir}")
    
    for entry in os.scandir(mods_dir):
        if entry.is_file():
            if entry.name.endswith('.pw.toml') or entry.name.endswith('.jar'):
                mod_name = get_mod_name(entry.name)
                file_type = "TOML" if entry.name.endswith('.pw.toml') else "JAR"
                print(f"找到{file_type}文件: {entry.name} -> Mod名称: {mod_name}")
                mod_names.append(mod_name)
    
    return mod_names

def confirm_execution(mod_names):
    """确认是否执行命令"""
    print("\n找到以下Mods:")
    for i, name in enumerate(mod_names, 1):
        print(f"{i}. {name}")
    
    while True:
        answer = input("\n是否要执行packwiz命令添加这些Mod? (y/n): ").lower()
        if answer in ('y', 'yes'):
            return True
        elif answer in ('n', 'no'):
            return False
        print("请输入y或n")

def run_packwiz_command(cmd, work_dir, max_retries=3):
    """执行packwiz命令，自动处理交互和重试"""
    for attempt in range(1, max_retries + 1):
        try:
            process = subprocess.Popen(
                cmd,
                cwd=work_dir,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                bufsize=1  # 行缓冲
            )
            
            # 自动回答"Y"到标准输入
            stdout, stderr = process.communicate(input='Y\n', timeout=10)
            
            # 合并stdout和stderr输出，因为packwiz可能将错误输出到stdout
            full_output = stdout + stderr
            
            if process.returncode == 0:
                return True, full_output.strip()
            else:
                return False, full_output.strip()
                
        except subprocess.TimeoutExpired:
            process.kill()
            if attempt < max_retries:
                print(f"命令超时，正在重试({attempt}/{max_retries})...")
                time.sleep(1)
            else:
                return False, "命令执行超时"
        except Exception as e:
            return False, str(e)

def run_packwiz_commands(mod_names, work_dir, log_file):
    """执行packwiz命令并记录日志"""
    with open(log_file, 'w', encoding='utf-8') as log:
        log.write(f"Packwiz命令执行日志 - {datetime.now()}\n\n")
        
        for name in mod_names:
            cmd = f"packwiz mr add {name}"
            print_step(f"正在执行: {cmd}")
            log.write(f"执行: {cmd}\n")
            
            success, output = run_packwiz_command(cmd, work_dir)
            
            if success:
                if output:  # 只有有输出时才打印
                    print(output)
                log.write(f"成功:\n{output}\n")
            else:
                error_msg = output if output else "未知错误(无错误输出)"
                print(f"错误: {error_msg}", file=sys.stderr)
                log.write(f"失败:\n{error_msg}\n")
            
            log.write("-" * 50 + "\n")

def main():
    parser = argparse.ArgumentParser(description='自动添加mod到packwiz')
    parser.add_argument('mods_dir', help='包含mod文件的目录路径')
    parser.add_argument('work_dir', help='执行packwiz命令的工作目录')
    args = parser.parse_args()

    # 验证路径
    mods_dir = pathlib.Path(args.mods_dir).resolve()
    work_dir = pathlib.Path(args.work_dir).resolve()
    
    if not mods_dir.exists():
        print(f"错误: Mods目录不存在: {mods_dir}", file=sys.stderr)
        sys.exit(1)
    
    if not work_dir.exists():
        print(f"错误: 工作目录不存在: {work_dir}", file=sys.stderr)
        sys.exit(1)

    # 生成日志文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"log-{timestamp}.txt"

    # 执行主要逻辑
    mod_names = scan_mods(mods_dir)
    if not mod_names:
        print("没有找到有效的Mods", file=sys.stderr)
        sys.exit(1)
    
    if confirm_execution(mod_names):
        run_packwiz_commands(mod_names, work_dir, log_file)
        print(f"\n完成。日志已保存到 {log_file}")
    else:
        print("已取消操作")

if __name__ == '__main__':
    main()