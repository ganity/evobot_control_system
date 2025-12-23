"""
打包优化脚本 - 用于减小打包后的文件体积
"""

import os
import shutil
from pathlib import Path


def optimize_build():
    """优化构建结果"""
    dist_path = Path("dist/EvoBot控制系统")
    
    if not dist_path.exists():
        print("未找到构建结果目录")
        return
    
    print("开始优化构建结果...")
    
    # 删除不需要的文件
    unnecessary_files = [
        "*.pyd.bak",
        "*.dll.bak", 
        "*test*",
        "*Test*",
        "unittest*",
        "pytest*",
    ]
    
    # 删除不需要的目录
    unnecessary_dirs = [
        "test",
        "tests", 
        "Test",
        "unittest",
        "pytest",
        "__pycache__",
    ]
    
    total_saved = 0
    
    # 遍历所有文件
    for root, dirs, files in os.walk(dist_path):
        # 删除不需要的目录
        for dir_name in dirs[:]:
            if any(pattern in dir_name.lower() for pattern in unnecessary_dirs):
                dir_path = Path(root) / dir_name
                if dir_path.exists():
                    size = sum(f.stat().st_size for f in dir_path.rglob('*') if f.is_file())
                    shutil.rmtree(dir_path)
                    total_saved += size
                    print(f"删除目录: {dir_path}")
                    dirs.remove(dir_name)
        
        # 删除不需要的文件
        for file_name in files:
            if any(pattern.replace('*', '') in file_name.lower() for pattern in unnecessary_files):
                file_path = Path(root) / file_name
                if file_path.exists():
                    size = file_path.stat().st_size
                    file_path.unlink()
                    total_saved += size
                    print(f"删除文件: {file_path}")
    
    print(f"优化完成，节省空间: {total_saved / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    optimize_build()