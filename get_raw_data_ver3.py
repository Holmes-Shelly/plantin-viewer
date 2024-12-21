# 用来获取原始数据
# 在根目录下按照yyyymmdd格式，每天一个文件夹，每个文件夹里有近5800个raw文件
# 目前已产生近100个工作日的存档文件夹，后面会增加到1000个文件夹
# 每个raw文件能输出1314对数据和质量码，数据用float格式储存，质量码用int格式储存
# 
import os
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime
import logging
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
import numpy as np
from tqdm import tqdm
import pandas as pd

def parse_raw_file(file_path):
    """解析单个raw文件并返回数据"""
    try:
        with open(file_path, 'r') as f:
            filename = os.path.basename(file_path)
            timestamp = datetime.strptime(filename.split('_')[1].split('.')[0], '%Y%m%d%H%M%S')
            
            # 跳过前3行
            for _ in range(3):
                next(f)
            
            for line_num, line in enumerate(f, start=4):  # 从第4行开始计数
                line = line.strip()
                if not line or line in ['Dx', 'Ax']:
                    continue
                    
                try:
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            # 数据用float格式，质量码用int格式
                            value = float(parts[2])
                            quality = int(parts[3])
                            yield timestamp, parts[1], value, quality
                        except ValueError:
                            logging.warning(f"无法转换数值: {parts[2]} 在文件 {filename} 第 {line_num} 行: '{line}'")
                            continue
                except (ValueError, IndexError) as e:
                    logging.warning(f"文件 {filename} 第 {line_num} 行解析失败: '{line}' - 错误: {str(e)}")
                    continue
    except Exception as e:
        logging.error(f"处理文件出错 {file_path}: {str(e)}")

def process_file_batch(args):
    """处理一批文件并写入临时parquet文件"""
    file_batch, batch_id, tag_names = args
    
    # 使用字典存储数据和质量码
    data_dict = {}
    
    for file_path in file_batch:
        filename = os.path.basename(file_path)
        for timestamp, tag, value, quality in parse_raw_file(file_path):
            if timestamp not in data_dict:
                data_dict[timestamp] = {}
                for tag_name in tag_names:
                    data_dict[timestamp][f'{tag_name}_value'] = np.nan
                    data_dict[timestamp][f'{tag_name}_quality'] = 0
            
            data_dict[timestamp][f'{tag}_value'] = value
            data_dict[timestamp][f'{tag}_quality'] = quality
    
    # 转换为DataFrame
    df = pd.DataFrame.from_dict(data_dict, orient='index')
    
    # 创建多层列索引
    columns = pd.MultiIndex.from_tuples(
        [(col.rsplit('_', 1)[0], col.rsplit('_', 1)[1]) 
         for col in df.columns],
        names=['tag', 'type']
    )
    df.columns = columns
    
    # 保存临时文件
    temp_path = os.path.join('temp_parquet', f'temp_batch_{batch_id}.parquet')
    df.to_parquet(temp_path)

def fetch_data():
    """获取并处理数据"""
    root_folder = "."
    MAX_FILE_SIZE = 1 * 1024 * 1024 * 1024  # 1GB
    
    # 创建临时目录
    temp_dir = "temp_parquet"
    if os.path.exists(temp_dir):
        for file in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, file))
    else:
        os.makedirs(temp_dir)
    
    # 集所有需要处理的文件
    all_files = []
    print("正在收集文件...")
    for folder_name in os.listdir(root_folder):
        if not os.path.isdir(os.path.join(root_folder, folder_name)):
            continue
        try:
            datetime.strptime(folder_name, '%Y%m%d')
        except ValueError:
            continue
            
        folder_path = os.path.join(root_folder, folder_name)
        for file_name in os.listdir(folder_path):
            if file_name.endswith('.raw'):
                all_files.append(os.path.join(folder_path, file_name))
    
    if not all_files:
        print("未找到任何raw文件")
        return False
        
    # 从第一个文件获取tag_names
    tag_names = []
    print("从第一个文件获取tag列表...")
    with open(all_files[0], 'r') as f:
        for _ in range(3):
            next(f)
        for line in f:
            line = line.strip()
            if not line or line in ['Dx', 'Ax']:
                continue
            parts = line.split()
            if len(parts) >= 4:
                tag_names.append(parts[1])
    
    print(f"共获取到 {len(tag_names)} 个tag")
    
    # 增加次大小，减少文件数量
    batch_size = 5000  # 增加到5000
    num_cores = min(mp.cpu_count(), 8)
    
    file_batches = [(all_files[i:i + batch_size], i // batch_size, tag_names) 
                    for i in range(0, len(all_files), batch_size)]
    
    print(f"将使用 {num_cores} 个进程处理数据，每批 {batch_size} 个文件")
    
    try:
        with ProcessPoolExecutor(max_workers=num_cores) as executor:
            list(tqdm(
                executor.map(process_file_batch, file_batches),
                total=len(file_batches),
                desc="处理进度"
            ))
        
        # 合并临时文件
        print("正在合并数据文件...")
        temp_files = [f for f in os.listdir(temp_dir) if f.endswith('.parquet')]
        
        # 用于按月分组的字典
        monthly_dfs = {}
        
        print(f"找到 {len(temp_files)} 个临时文件待合并")
        
        for temp_file in tqdm(temp_files, desc="合并文件进度"):
            try:
                temp_path = os.path.join(temp_dir, temp_file)
                df = pd.read_parquet(temp_path)
                
                # 按月分组
                for date, group in df.groupby(df.index.to_period('M')):
                    month_key = date.strftime('%Y%m')
                    if month_key not in monthly_dfs:
                        monthly_dfs[month_key] = []
                    monthly_dfs[month_key].append(group)
                
            except Exception as e:
                print(f"处理文件 {temp_file} 时出错: {str(e)}")
                continue
        
        # 按月保存数据
        for month_key, dfs in monthly_dfs.items():
            try:
                print(f"处理 {month_key} 的数据...")
                final_df = pd.concat(dfs, axis=0)
                final_df.sort_index(inplace=True)
                output_file = f'data_matrix_{month_key}.parquet'
                final_df.to_parquet(output_file)
                print(f"已生成数据文件: {output_file}")
            except Exception as e:
                print(f"保存 {month_key} 的数据时出错: {str(e)}")
        
        # 清理临时文件
        print("清理临时文件...")
        for file in os.listdir(temp_dir):
            try:
                os.remove(os.path.join(temp_dir, file))
            except Exception as e:
                print(f"删除临时文件 {file} 时出错: {str(e)}")
                
        os.rmdir(temp_dir)
        print("处理完成")
        
    except Exception as e:
        logging.error(f"处理文件时出错: {str(e)}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    fetch_data()