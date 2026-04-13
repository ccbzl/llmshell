#!/usr/bin/env python3
"""
扫描系统已安装的MCP Server并初始化servers.json文件
"""

import os
import json
import subprocess
import sys


def scan_python_packages():
    """
    扫描已安装的Python包，寻找MCP Server相关的包
    """
    print("=== 扫描已安装的Python包 ===")
    servers = []
    
    try:
        # 列出已安装的Python包
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            packages = result.stdout.strip().split('\n')
            for package in packages[2:]:  # 跳过表头
                parts = package.split()
                if len(parts) >= 2:
                    package_name = parts[0]
                    version = parts[1]
                    
                    # 查找包含mcp或server的包
                    if 'mcp' in package_name.lower() or 'server' in package_name.lower():
                        print(f"发现可能的MCP Server包: {package_name} (version: {version})")
                        servers.append({
                            "name": package_name,
                            "version": version,
                            "type": "python_package"
                        })
    except Exception as e:
        print(f"扫描Python包时出错: {e}")
    
    return servers


def scan_system_path():
    """
    扫描系统PATH中的可执行文件，寻找MCP Server相关的程序
    """
    print("\n=== 扫描系统PATH中的可执行文件 ===")
    servers = []
    
    try:
        path_dirs = os.environ.get('PATH', '').split(os.pathsep)
        for path_dir in path_dirs:
            if os.path.exists(path_dir):
                for filename in os.listdir(path_dir):
                    file_path = os.path.join(path_dir, filename)
                    if os.path.isfile(file_path) and os.access(file_path, os.X_OK):
                        # 查找包含mcp或server的可执行文件
                        if 'mcp' in filename.lower() or 'server' in filename.lower():
                            print(f"发现可能的MCP Server可执行文件: {file_path}")
                            servers.append({
                                "name": filename,
                                "path": file_path,
                                "type": "executable"
                            })
    except Exception as e:
        print(f"扫描系统PATH时出错: {e}")
    
    return servers


def create_servers_json(servers):
    """
    创建并初始化servers.json文件
    """
    print("\n=== 创建servers.json文件 ===")
    
    # 创建mcp目录
    mcp_dir = os.path.expanduser("~/.llmshell/mcp")
    os.makedirs(mcp_dir, exist_ok=True)
    
    # 构建配置
    configs = {}
    for server in servers:
        server_name = server.get('name')
        if server_name:
            # 构建基本配置
            config = {
                "command": sys.executable,
                "args": ["-m", server_name],
                "env": {}
            }
            configs[server_name] = config
            print(f"添加配置: {server_name}")
    
    # 写入servers.json文件
    servers_json_path = os.path.join(mcp_dir, "servers.json")
    try:
        with open(servers_json_path, 'w') as f:
            json.dump(configs, f, indent=2)
        print(f"\n成功创建servers.json文件: {servers_json_path}")
        print(f"添加了 {len(configs)} 个MCP Server配置")
        return True
    except Exception as e:
        print(f"创建servers.json文件时出错: {e}")
        return False


def main():
    """
    主函数
    """
    print("开始扫描系统已安装的MCP Server...")
    
    # 扫描Python包
    python_servers = scan_python_packages()
    
    # 扫描系统PATH
    system_servers = scan_system_path()
    
    # 合并结果
    all_servers = python_servers + system_servers
    
    if not all_servers:
        print("\n未发现任何MCP Server")
        return
    
    # 创建servers.json文件
    create_servers_json(all_servers)


if __name__ == "__main__":
    main()
