import numpy as np
import torch
import argparse
import os

# Offline mode: monkey-patch torch.hub._parse_repo_info to skip GitHub API calls
# and resolve branch name directly from local cache
torch.hub.set_dir('/workspace/torch_cache/hub')
_original_parse_repo_info = torch.hub._parse_repo_info


def _patched_parse_repo_info(github):
    repo_owner, repo_name = github.split('/')
    hub_dir = torch.hub.get_dir()
    for possible_ref in ("main", "master"):
        if os.path.exists(f"{hub_dir}/{repo_owner}_{repo_name}_{possible_ref}"):
            return repo_owner, repo_name, possible_ref
    raise RuntimeError(
        f"Offline: repo {github} not found in cache ({hub_dir}). "
        "Download it first with network access."
    )


torch.hub._parse_repo_info = _patched_parse_repo_info

from src import config
from src.slam import SLAM
from src.utils.datasets import get_dataset
from time import gmtime, strftime
from colorama import Fore,Style
from torch.utils.tensorboard import SummaryWriter

import random
def setup_seed(seed):
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    random.seed(seed)
    torch.backends.cudnn.deterministic = True

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, help='Path to config file.')
    parser.add_argument('--run_name', type=str, default=None,
                        help='Custom name for this run (default: auto-generate timestamp).')
    args = parser.parse_args()

    torch.multiprocessing.set_start_method('spawn')

    cfg = config.load_config(args.config)

    if args.run_name:
        run_tag = args.run_name
    else:
        run_tag = strftime("%Y%m%d_%H%M%S", gmtime())
    cfg['scene'] = f"{cfg['scene']}/{run_tag}"

    setup_seed(cfg['setup_seed'])
    if cfg['fast_mode']:
        # Force the final refine iterations to be 3000 if in fast mode
        cfg['mapping']['final_refine_iters'] = 3000

    output_dir = cfg['data']['output']
    output_dir = output_dir+f"/{cfg['scene']}"

    # clean the rerun_stream.rrd
    if os.path.exists(f"{output_dir}/rerun_stream.rrd"):
        os.remove(f"{output_dir}/rerun_stream.rrd")

    start_time = strftime("%Y-%m-%d %H:%M:%S", gmtime())
    start_info = "-"*30+Fore.YELLOW+\
                 f"\nStart WildGS-SLAM at {start_time},\n"+Style.RESET_ALL+ \
                 f"   scene: {cfg['dataset']}-{cfg['scene']},\n" \
                 f"   output: {output_dir}\n"+ \
                 "-"*30
    print(start_info)
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    config.save_config(cfg, f'{output_dir}/cfg.yaml')

    dataset = get_dataset(cfg)

    slam = SLAM(cfg,dataset)
    slam.run()

    end_time = strftime("%Y-%m-%d %H:%M:%S", gmtime())
    print("-"*30+Fore.LIGHTRED_EX+f"\nWildGS-SLAM finishes!\n"+Style.RESET_ALL+f"{end_time}\n"+"-"*30)

