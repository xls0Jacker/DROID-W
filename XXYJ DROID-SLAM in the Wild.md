_[CVPR 2026]_

<font style="color:rgb(0, 0, 0);">论文链接：</font>[https://arxiv.org/abs/2603.19076](https://arxiv.org/abs/2603.19076)_<font style="color:rgb(0, 0, 0);">  
</font>_<font style="color:#000000;">项目链接：</font>[https://moyangli00.github.io/droid-w/](https://moyangli00.github.io/droid-w/)；[https://github.com/MoyangLi00/DROID-W](https://github.com/MoyangLi00/DROID-W)

# 论文内容概述
**摘要**——<u>我们提出了一种鲁棒的实时 RGB SLAM 系统，通过引入 可微分的不确定性感知束束调整（Uncertainty-aware Bundle Adjustment） 来处理动态环境</u>。传统 SLAM 方法通常假设场景是静态的，因此在存在运动物体时容易出现跟踪失败。近年来，一些动态 SLAM 方法尝试通过预定义的动态先验或不确定性感知建图来解决这一问题，但在面对未知动态物体或高度杂乱的场景时，这些方法仍然存在局限性，因为此时几何建图往往变得不可靠。相比之下，我们的方法通过利用多视角视觉特征之间的不一致性来估计逐像素的不确定性，从而在真实动态环境中依然能够实现鲁棒的跟踪与重建。实验结果表明，该系统在复杂动态场景下能够实现最先进的相机位姿估计与场景几何重建效果，并且可以以约 10 FPS 的速度实现实时运行。

## Introduction
同时定位与建图（Simultaneous Localization and Mapping, SLAM）是计算机视觉中的一项基础任务，在自动驾驶 _[3, 12]_、机器人 _[1, 31, 69]_ 以及具身智能 _[5, 15, 24]_ 等领域具有广泛应用。尽管近年来取得了显著进展，但在真实世界环境中实现可靠的 SLAM 仍然具有挑战性。<u>动态和非刚性物体常常会破坏位姿估计和三维重建</u>，从而限制了 SLAM 系统在实际应用中的鲁棒性和适用性。

<details class="lake-collapse"><summary id="ue0bd38ca"><em><span class="ne-text">[3, 12]</span></em></summary><p id="u761932d3" class="ne-p"><span class="ne-text">[3] Self-driving Cars: A Survey（Expert Systems with Applications, 2021）：系统综述自动驾驶领域的发展脉络与关键技术，涵盖感知、定位、规划与控制等模块，对比分析传统方法与深度学习方法的优劣，为自动驾驶系统的整体架构设计提供全面参考。</span></p><p id="uf1422661" class="ne-p"><span class="ne-text">[12] Vision Meets Robotics: The KITTI Dataset（International Journal of Robotics Research, 2013）：提出KITTI Dataset这一面向自动驾驶的多模态基准数据集，包含立体视觉、激光雷达与GPS/IMU数据，推动了视觉里程计、目标检测与SLAM等任务的发展，成为自动驾驶领域最具影响力的标准评测平台之一。</span></p></details>
<details class="lake-collapse"><summary id="ubd4fda69"><em><span class="ne-text">[1, 31, 69]</span></em></summary><p id="u1a36c342" class="ne-p"><span class="ne-text">[1] Scientific Exploration of Challenging Planetary Analog Environments with a Team of Legged Robots（Science Robotics, 2023）：提出一种面向类行星极端环境的多足机器人协同探索系统，通过多机器人协作感知与自主导航，实现复杂地形下的稳定移动与科学探测，验证了多机器人系统在未知环境中的高鲁棒性与任务执行能力。</span></p><p id="u27349fac" class="ne-p"><span class="ne-text">[31] SlideSLAM: Sparse, Lightweight, Decentralized Metric-Semantic SLAM for Multi-Robot Navigation（arXiv, 2024）：提出一种稀疏、轻量级且去中心化的多机器人SLAM框架SlideSLAM，将度量SLAM与语义信息融合，在保证精度的同时显著降低通信与计算开销，适用于资源受限的多机器人协同导航场景。</span></p><p id="ud395b105" class="ne-p"><span class="ne-text">[69] Swarm of Micro Flying Robots in the Wild（Science Robotics, 2022）：实现了微型无人机集群在真实户外环境中的自主飞行与协同控制，通过分布式感知与规划方法，使大规模机器人集群能够在复杂动态环境中完成稳定编队与任务执行，展示了群体智能系统的实际应用潜力。</span></p></details>
<details class="lake-collapse"><summary id="u291e49fb"><em><span class="ne-text">[5, 15, 24]</span></em></summary><p id="u6b1f859e" class="ne-p"><span class="ne-text">[5] How to Not Train Your Dragon: Training-Free Embodied Object Goal Navigation with Semantic Frontiers（arXiv, 2023）：提出一种无需训练的具身目标导航方法，通过引入语义前沿（semantic frontiers）机制，将场景语义信息与探索策略结合，在未知环境中实现高效目标搜索，避免了传统方法对大规模训练数据的依赖。</span></p><p id="u0bffe9b0" class="ne-p"><span class="ne-text">[15] EgoDex: Learning Dexterous Manipulation from Large-Scale Egocentric Video（arXiv, 2025）：提出EgoDex框架，利用大规模第一视角视频数据学习灵巧操作技能，通过从人类操作中提取动作与视觉关联，实现机器人在复杂操作任务中的泛化能力提升。</span></p><p id="uaede17b6" class="ne-p"><span class="ne-text">[24] Benchmarking Egocentric Visual-Inertial SLAM at City Scale（IEEE/CVF International Conference on Computer Vision, 2025）：构建面向城市级规模的第一视角视觉-惯性SLAM基准，系统评估现有方法在长时序、大范围场景中的性能表现，揭示了尺度漂移、动态干扰等关键问题，为后续SLAM系统设计提供标准化评测依据。</span></p></details>
尽管这一任务已被广泛研究，<u>许多现有方法</u> _[10, 34–36, 48, 49]_<u> 仍然假设环境是静态的，并忽略非刚性运动，这会在相机跟踪和场景重建中同时引入误差</u>。<u>一些近期工作</u> _[4, 18, 44, 55, 57]_ <u>试图通过检测或分割运动物体并将这些区域进行掩蔽来处理动态场景。然而，这类方法在很大程度上依赖于对动态物体的先验知识，从而限制了其在复杂多样的真实世界环境中的鲁棒性</u>。

<details class="lake-collapse"><summary id="ue1224d76"><em><span class="ne-text">[10, 34–36, 48, 49]</span></em><span class="ne-text" style="text-decoration: underline"></span></summary><p id="uc2aae789" class="ne-p"><span class="ne-text">[10] Direct Sparse Odometry（IEEE Transactions on Pattern Analysis and Machine Intelligence, 2017）：提出直接法稀疏视觉里程计（DSO），通过最小化光度误差在像素层面进行优化，仅选择高梯度像素进行建模，实现高精度、实时的单目位姿估计，避免了特征提取与匹配带来的信息损失。</span></p><p id="u04ea5f94" class="ne-p"><span class="ne-text">[34] ORB-SLAM2: An Open-Source SLAM System for Monocular, Stereo, and RGB-D Cameras（IEEE Transactions on Robotics, 2017）：提出通用开源SLAM系统ORB-SLAM2，支持单目、双目与RGB-D输入，集成回环检测、重定位与全局优化模块，在精度、鲁棒性与实时性之间取得良好平衡，成为经典基准方法之一。</span></p><p id="u7fb6c1df" class="ne-p"><span class="ne-text">[35] ORB-SLAM: A Versatile and Accurate Monocular SLAM System（IEEE Transactions on Robotics, 2015）：提出ORB-SLAM，基于ORB特征构建完整单目SLAM系统，引入关键帧管理、闭环检测与图优化机制，实现高精度与高鲁棒性的实时定位与建图。</span></p><p id="uba59e247" class="ne-p"><span class="ne-text">[36] KinectFusion: Real-Time Dense Surface Mapping and Tracking（IEEE International Symposium on Mixed and Augmented Reality, 2011）：提出KinectFusion系统，利用深度相机实现实时稠密三维重建，通过TSDF体素融合与ICP配准完成相机跟踪与场景建模，开创了实时稠密SLAM的发展方向。</span></p><p id="ub27939e0" class="ne-p"><span class="ne-text">[48] DROID-SLAM: Deep Visual SLAM for Monocular, Stereo, and RGB-D Cameras（NeurIPS, 2021）：提出基于深度学习的端到端SLAM系统DROID-SLAM，通过循环网络与全局优化模块联合建模数据关联与位姿估计，在多种输入模态下显著提升跟踪精度与鲁棒性。</span></p><p id="u84e32039" class="ne-p"><span class="ne-text">[49] Deep Patch Visual Odometry（NeurIPS, 2023）：提出基于深度学习的Patch级视觉里程计方法，通过学习局部图像块之间的匹配与几何关系，提高在弱纹理和复杂光照条件下的位姿估计鲁棒性。</span></p></details>
<details class="lake-collapse"><summary id="u4df9e662"><em><span class="ne-text">[4, 18, 44, 55, 57]</span></em><span class="ne-text"></span></summary><p id="uf85beca3" class="ne-p"><span class="ne-text">[4] DynaSLAM: Tracking, Mapping and Inpainting in Dynamic Scenes（IEEE Robotics and Automation Letters, 2018）：提出DynaSLAM，通过结合语义分割与多视几何方法检测并剔除动态物体，同时利用图像修复（inpainting）重建静态背景，从而在动态环境中实现鲁棒的相机跟踪与地图构建。</span></p><p id="u88c46323" class="ne-p"><span class="ne-text">[18] RoDyn-SLAM: Robust Dynamic Dense RGB-D SLAM with Neural Radiance Fields（IEEE Robotics and Automation Letters, 2024）：提出RoDyn-SLAM，将Neural Radiance Fields引入动态RGB-D SLAM，通过建模动态与静态场景的辐射场表示，实现高质量稠密重建与鲁棒位姿估计，适用于复杂动态环境。</span></p><p id="u6caca800" class="ne-p"><span class="ne-text">[44] DynaMon: Motion-Aware Fast and Robust Camera Localization for Dynamic Neural Radiance Fields（arXiv, 2023）：提出DynaMon方法，在NeRF框架下引入运动感知机制，通过显式建模动态区域的运动信息，提高相机定位在动态场景中的鲁棒性与效率。</span></p><p id="u565d670c" class="ne-p"><span class="ne-text">[55] ADD-SLAM: Adaptive Dynamic Dense SLAM with Gaussian Splatting（arXiv, 2025）：提出ADD-SLAM，将3D Gaussian Splatting引入动态SLAM，通过自适应建模动态与静态区域，实现高效稠密建图与实时渲染，在复杂动态环境中兼顾速度与精度。</span></p><p id="ubef4b8c2" class="ne-p"><span class="ne-text">[57] DG-SLAM: Robust Dynamic Gaussian Splatting SLAM with Hybrid Pose Optimization（NeurIPS, 2024）：提出DG-SLAM，基于3D Gaussian Splatting构建动态SLAM系统，并设计混合位姿优化策略（结合学习方法与几何优化），提升在动态场景中的跟踪稳定性与重建质量。</span></p></details>
近年来，<u>不确定性感知方法</u> _[25, 39, 66, 67]_ 在处理场景动态方面逐渐受到关注，因为它们<u>无需依赖预定义的运动先验</u>。这类方法<u>通常利用一个浅层多层感知机（MLP），从 DINO </u>_<u>[37]</u>_<u> 特征中估计逐像素的不确定性，并通过在线更新来优化预测器</u>。<u>然而，这些方法依赖于构建一个完全静态的神经隐式表示 </u>_<u>[33]</u>_<u> 或 Gaussian Splatting </u>_<u>[21]</u>_<u> 地图来进行不确定性优化。因此，在复杂的真实世界环境中，其性能仍然受到限制，因为动态和杂乱的场景会对稳定的场景表示带来显著挑战</u>。

<details class="lake-collapse"><summary id="u4fa15f1e"><em><span class="ne-text">[25, 39, 66, 67]</span></em></summary><p id="u8419074a" class="ne-p"><span class="ne-text">[25] WildGaussians: 3D Gaussian Splatting in the Wild（NeurIPS, 2024）：提出WildGaussians方法，将3D Gaussian Splatting扩展到无约束真实场景（in-the-wild），提升在复杂光照与非受控采集条件下的三维重建质量与泛化能力。</span></p><p id="uef2df5b8" class="ne-p"><span class="ne-text">[39] NeRF On-the-Go: Exploiting Uncertainty for Distractor-Free NeRFs in the Wild（CVPR, 2024）：提出NeRF On-the-Go方法，通过建模不确定性来识别并抑制干扰区域（如动态物体或噪声），从而在真实场景中获得更加干净、稳定的Neural Radiance Fields重建结果。</span></p><p id="u6b7f0e51" class="ne-p"><span class="ne-text">[66] WildGS-SLAM: Monocular Gaussian Splatting SLAM in Dynamic Environments（CVPR, 2025）：提出WildGS-SLAM，将3D Gaussian Splatting引入单目SLAM框架，并针对动态环境设计不确定性建模与优化策略，实现鲁棒的相机跟踪与高质量稠密重建。</span></p><p id="ub2202217" class="ne-p"><span class="ne-text">[67] UP-SLAM: Adaptively Structured Gaussian SLAM with Uncertainty Prediction in Dynamic Environments（arXiv, 2025）：提出UP-SLAM，通过自适应结构建模与不确定性预测机制，动态调整Gaussian表示与优化过程，从而提升在复杂动态场景中的SLAM鲁棒性与重建精度。</span></p></details>
<details class="lake-collapse"><summary id="uf87b8d32"><em><span class="ne-text">[37], [33], [21]</span></em></summary><p id="uf1d722f2" class="ne-p"><span class="ne-text">[37] DINOv2: Learning Robust Visual Features without Supervision（arXiv, 2023）：提出DINOv2自监督视觉表示学习方法，通过大规模无标注数据训练获得高鲁棒性的通用视觉特征，在多种下游任务中表现出强泛化能力。</span></p><p id="uc8c825aa" class="ne-p"><span class="ne-text">[33] NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis（ECCV, 2020）：提出Neural Radiance Fields表示方法，将三维场景建模为连续隐式辐射场，实现高质量新视角合成，开创了基于神经隐式表示的三维重建范式。</span></p><p id="ueeff8745" class="ne-p"><span class="ne-text">[21] 3D Gaussian Splatting for Real-Time Radiance Field Rendering（ACM Transactions on Graphics, 2023）：提出3D Gaussian Splatting方法，以显式高斯表示替代隐式NeRF建模，实现高质量、实时的三维场景渲染，大幅提升渲染效率并降低计算开销。</span></p></details>
<u>为了解决上述局限性，我们提出了 DROID-W</u>，这是一种新颖的动态感知 SLAM 系统，<u>将现有的深度视觉 SLAM 系统 DROID-SLAM 扩展到动态环境中</u>。我们将不确定性优化引入到可微分的束调整（BA）层中，以迭代更新动态不确定性、相机位姿以及场景几何结构。通过利用多视角视觉特征相似性，可以对每一帧的逐像素不确定性进行更新。<u>与以往方法不同，我们的不确定性估计不再依赖于高质量的几何建图或预定义的运动先验</u>。<u>此外，我们还引入了 DROID-W 数据集，该数据集包含多样且无约束的室外动态场景，并进一步加入了来自 YouTube 的视频片段，用于真正“野外环境”（in-the-wild）的评估</u>。不同于以往工作中已经趋于饱和的室内基准数据集，我们的数据序列涵盖了具有多种物体动态的复杂真实场景。实验结果表明，我们的方法在真实环境中能够实现鲁棒的不确定性估计，从而在相机跟踪精度和场景几何重建方面达到当前最先进水平，并且可以以约 10 FPS 的速度实现实时运行。

## Related Works
### Traditional Visual SLAM
<u>许多现有的传统视觉 SLAM 方法</u> _[9, 10, 34, 35, 48, 49]_ <u>假设环境是静态的，这往往会导致特征匹配错误，并降低跟踪精度和建图质量</u>。为缓解物体运动带来的干扰，<u>一些早期工作 </u>_<u>[22, 23]</u>_<u> 通过在优化过程中对帧间较大的残差进行惩罚，从而隐式地处理动态元素</u>。<u>其他的一些方法 </u>_<u>[38, 45]</u>_<u> 则基于帧与模型对齐的残差来识别动态区域</u>。StaticFusion _[45]_ 通过关键点聚类和帧到模型对齐来检测具有较大残差的区域，并引入惩罚项以约束地图仅包含静态区域。ReFusion _[38]_ 采用 TSDF _[8]_ 表示，并移除具有较大深度残差的不确定区域，以维持一致的背景地图。

<u>另一类</u>_<u>互补</u>_<u>方法 </u>_<u>[4, 40, 41, 60, 68]</u>_<u> 利用目标检测与分割来显式地过滤动态区域</u>。DynaSLAM _[4]_ 和 DS-SLAM _[60]_ 均基于 ORB-SLAM2 _[34]_，通过分割网络 _[2, 14]_ 检测运动物体并重建静态背景。Detect-SLAM _[68]_ 集成了 SSD 检测器 _[30]_，并传播关键点的运动概率以降低目标检测带来的延迟。CoFusion _[40]_ 和 MaskFusion _[41]_ 进一步扩展到对象级别，能够对多个独立运动的物体进行联合分割、跟踪与重建。FlowFusion _[63]_ 则利用光流残差来突出动态区域。

<details class="lake-collapse"><summary id="u811b7c58"><em><span class="ne-text">互补</span></em><span class="ne-text">：之前的一类方法是在几何上进行改进，而这一类方法补充了语义信息。</span></summary><p id="uf1ffa3fa" class="ne-p"><img src="https://cdn.nlark.com/yuque/0/2026/png/45861457/1777252117114-b9408914-aefd-4667-9b20-663a4b60e24e.png" width="869.647030945881" title="" crop="0,0,1,1" id="ub926d3a9" class="ne-image"></p></details>
### NeRF- and GS-based SLAM
近年来，神经辐射场（Neural Radiance Fields, NeRF）_[33]_ 的进展因其致密表示和逼真渲染能力，在 SLAM 系统中的应用受到了广泛关注。开创性工作 iMAP _[47] _提出了首个基于神经隐式表示的 SLAM 框架，实现了高质量的稠密建图。然而，由于使用单一的多层感知机（MLP）来表示整个场景，iMAP _[47]_ 存在细节丢失和灾难性遗忘的问题。为了解决这些局限性，NICE-SLAM _[70]_ 引入了分层特征网格，以提升系统的可扩展性和重建精度。随后的一系列方法 _[19, 42, 51, 59, 64, 71]_ 进一步在效率和鲁棒性方面对该类 SLAM 系统进行了改进。最近，3D 高斯 Splatting（3DGS）_[21]_ 的兴起也启发了大量 SLAM 方法 _[13, 16, 20, 32, 43, 58]_，这些方法采用高斯基元进行建模。然而，这类方法通常仍然假设环境大多是静态的，从而限制了其在包含动态物体的真实场景中的应用能力。

为了解决这一局限性，<u>近年来提出了多种基于动态 NeRF 的方法</u> _[18, 26, 44, 56]_ <u>以及基于 GS 的 SLAM 系统</u> _[27, 29, 55, 57, 66, 67]_。<u>其中，大多数方法</u> _[26, 27, 29, 55]_ <u>依赖目标检测或语义分割来对动态区域进行掩蔽，但在处理未定义或未见过的物体类别时往往表现不佳</u>。为此，DynaMoN _[44]_ 引入了一个额外的 CNN，通过前向光流预测运动掩码；而 RoDyn-SLAM _[18]_ 和 DG-SLAM _[57]_ 则将语义分割与变形掩码（warping masks）相结合，以提升运动掩码的估计效果。WildGS-SLAM _[66]_ 和 UP-SLAM _[67]_ 采用不确定性建模来处理场景动态问题。它们利用一个浅层 MLP，从 DINOv2 _[37]_ 特征中估计逐像素的运动不确定性，因为这些特征对外观变化具有鲁棒性，并能够表达丰富的语义信息。该不确定性 MLP 在输入图像与渲染图像之间的光度和深度损失监督下进行优化。此外，UP-SLAM _[67]_ 还将高维视觉特征扩展到 3DGS 特征空间中，并引入相似性损失作为额外的不确定性约束。

然而，<u>这些方法中的不确定性优化仍然与场景表示紧密耦合，这在建图过程受限的复杂环境中会导致性能下降</u>。<u>相比之下，我们的方法通过利用帧间视觉特征相似性来估计动态不确定性，在具有挑战性的真实世界环境中表现出更强的鲁棒性与有效性</u>。

### Feed-forward Approaches
<u>近年来，基于前向传播（feed-forward）的重建与位姿估计方法取得了显著进展</u>。DUSt3R _[54]_ 和 VGGT _[52]_ 在场景几何估计方面表现出较强的性能。MonST3R _[62]_ 将 DUSt3R _[54]_ 扩展到动态环境，通过从光流与点图中估计动态掩码来处理运动信息。Easi3R _[6]_ 提出了一种无需训练的 4D 重建框架，通过从 DUSt3R _[54]_ 的注意力图中分离运动信息来实现动态建模。然而，这些方法通常仅适用于短序列。CUT3R_ [53]_ 和 TTT3R _[7]_ 进一步推进了前向重建方法，使其能够以在线连续方式处理长序列数据。<u>尽管这些方法能够生成视觉上较为逼真的几何结果，但与基于 SLAM 的系统相比，纯前向传播管线在恢复精确相机轨迹以及度量一致的场景结构方面仍然存在困难</u>。<u>相比之下，我们的方法基于视觉 SLAM 框架，在相机轨迹估计与场景重建方面能够取得更高的精度与一致性</u>。

## Proposed Method
<u>我们的方法基于先前的深度视觉 SLAM 系统 DROID-SLAM </u>_<u>[48]</u>_<u> 进行改进，引入了可微分的不确定性感知束调整（Uncertainty-aware Bundle Adjustment, UBA），显式地建模逐像素不确定性，以应对动态物体的影响</u>。对于来自复杂真实场景的 RGB 序列，本系统联合优化相机位姿、深度以及不确定性，从而实现鲁棒的跟踪以及高精度的几何估计。

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777101757143-ab8133f1-6818-4878-9505-3169f9f975e6.png)

**图 2. 系统概述**。所提出的 DROID-W 以一段 RGB 图像序列作为输入，同时估计相机位姿并恢复场景几何结构。该系统以迭代方式交替执行位姿-深度细化与不确定性优化。所提出的不确定性感知稠密束调整通过逐像素不确定性$ u $对重投影残差进行加权，从而减弱动态干扰物的影响。此外，我们使用预测的单目深度$ \mathbf{D} $作为束调整的正则化项，以提升其在高度动态环境下的鲁棒性。对于不确定性优化模块，我们首先从输入图像中提取 DINOv2 _[37]_ 特征，然后利用多视角特征一致性迭代更新动态不确定性图。具体而言，特征一致性通过图像$ \mathbf{I}_i $及其在图像$ \mathbf{I}_j $中对应特征之间的余弦相似度来度量，其中刚体运动对应关系$ \mathbf{p}_{ij} $由当前的位姿与深度估计得到。

接下来，我们首先总结针对静态环境设计的 DROID-SLAM 的关键组成部分（第 3.1 节）。随后介绍我们提出的可微分不确定性感知束调整（Differentiable Uncertainty-aware Bundle Adjustment, UBA）（第 3.2 节）以及动态不确定性更新模块（第 3.3 节）。最后，我们给出所提出的整体动态 SLAM 系统（第 3.4 节）。<u>DROID-W 的整体框架如</u>_<u>图 2</u>_<u> 所示</u>。

### Preliminaries
<u>DROID-SLAM 利用可微分的束调整（Differentiable Bundle Adjustment, BA）层以迭代方式更新相机位姿与深度</u>。对于输入序列中的每一帧 RGB 图像$ \{\mathbf{I}_t\}_{t=0}^{N} $，系统维护两个状态变量：相机位姿$ \mathbf{G}_t \in SE(3) $，以及_逆深度_$ \mathbf{d}_t \in \mathcal{R}^{\frac{H}{8} \times \frac{W}{8}} $。此外，系统构建帧图（frame-graph）$ (\mathcal{V}, \mathcal{E}) $来表示帧间的共视关系，其中边$ (i, j) \in \mathcal{E} $表示图像$ \mathbf{I}_i $与$ \mathbf{I}_j $存在重叠区域。相机位姿集合$ \{\mathbf{G}_t\}_{t=0}^{N} $与逆深度集合$ \{\mathbf{d}_t\}_{t=0}^{N} $通过可微分 BA 层进行迭代更新，该过程作用于一组图像对$ (\mathbf{I}_i, \mathbf{I}_j) $。

<details class="lake-collapse"><summary id="u7f273160"><em><span class="ne-text">逆深度</span></em><span class="ne-text"> ：深度无穷远处难以表示，化为分数（/逆深度）后可较好表示。</span></summary><p id="ue914d4f0" class="ne-p"><img src="https://cdn.nlark.com/yuque/0/2026/png/45861457/1777253045045-45593cf4-45ab-4ae7-b674-763c3e8fbcd9.png" width="810.7562765311785" title="" crop="0,0,1,1" id="uad268845" class="ne-image"></p></details>
#### Differential Bundle Adjustment
对于每一对图像$ (\mathbf{I}_i, \mathbf{I}_j) $，可以推导其刚体运动对应关系如下：

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777102397141-e2228b6b-bad2-4a45-8389-dc110bc3e394.png)

其中$ \Pi_c $表示相机投影函数，$ \mathbf{G}'_{ij} $表示帧$ i $与帧$ j $之间的相对位姿变量。变量$ \mathbf{p}_i \in \mathcal{R}^{\frac{H}{8} \times \frac{W}{8} \times 2} $表示帧$ i $中的像素坐标网格。DROID-SLAM 以迭代方式预测二维稠密对应关系$ \mathbf{p}^{*}_{ij} \in \mathcal{R}^{\frac{H}{8} \times \frac{W}{8} \times 2} $以及置信度图$ \mathbf{w}_{ij} \in \mathcal{R}^{\frac{H}{8} \times \frac{W}{8} \times 2} $。

可微分 BA 通过最小化稠密对应残差，联合优化相机位姿与逆深度，其形式如下：

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777102587359-f442d57a-9a8c-4936-b88d-4154a9de3157.png)

其中$ ||\cdot||_{\Sigma} $表示马氏距离（Mahalanobis distance），用于根据 DROID-SLAM 预测的置信度图对残差进行加权。

相机位姿与视差通过高斯–牛顿（Gauss-Newton）算法进行优化，其更新形式如下：

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777102659522-90951832-90ec-4c02-ae73-a810015c7100.png)

其中$ (\mathbf{\Delta \xi}, \mathbf{\Delta d}) $表示位姿与视差的更新量。矩阵$ \mathbf{C} $为对角矩阵，因为_式 (2)_ 中的每一项仅依赖于单个深度值，因此其逆可以通过$ \mathbf{C}^{-1} = 1/\mathbf{C} $逐元素计算得到。

### Uncertainty-aware Bundle Adjustment
<u>动态物体违反了刚体运动假设，会产生不可靠的残差，从而破坏 DROID-SLAM 中 BA 层的稳定性。为了解决这一问题，我们引入逐像素动态不确定性</u>$ \mathbf{u}_t \in \mathcal{R}^{\frac{H}{8} \times \frac{W}{8}} $<u>，用于在优化过程中对不一致的对应关系进行降权处理</u>。<u>直观上，</u>$ \mathbf{u}_t $<u>作为一种置信度项，用于惩罚由动态物体引起的高残差</u>。因此，我们定义不确定性感知的马氏距离项$ ||\cdot||_{\Sigma^{\text{uncer}}_{ij}} $ 如下：

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777102868523-532658bc-dc99-47e5-b54d-c3d32f4ec0c8.png)

然而，<u>通过高斯–牛顿算法联合优化位姿、深度与不确定性在计算上代价过高</u>。<u>因此，我们采用一种交替优化策略，在位姿-深度细化与不确定性优化之间进行交替更新</u>。

位姿-深度细化通过最小化如下不确定性感知能量函数来进行：

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777102916707-834e7f3b-c211-4ace-a5f2-e057ed512a06.png)

### Uncertainty Optimization
<u>对于动态不确定性的优化，我们通过图像对之间 DINOv2 </u>_<u>[37]</u>_<u> 特征的相似性来度量多视角不一致性</u>，而不是采用_式 (5)_ 中的重投影残差。<u>在大幅动态运动情况下，重投影误差可能变得不可靠，而二维视觉特征相似性能够提供更加稳定且具有语义意义的多视角不一致性度量</u>。

#### Uncertainty Cost Function
对于每一对图像$ (\mathbf{I}_i, \mathbf{I}_j) $，首先使用 FiT3D _[61]_（一种改进的 DINOv2 模型）提取二维视觉特征$ (\mathbf{F}_i, \mathbf{F}_j) $。对于帧$ i $中的每个像素$ \mathbf{p}_i $，通过_式 (1) _计算其在帧$ j $中的刚体运动对应点$ \mathbf{p}_{ij} $。随后，通过双线性插值获得对应的特征$ \mathbf{F}_{ij} $以及不确定性$ \mathbf{u}_{ij} $。图像对的多视角一致性通过 DINOv2 特征$ \mathbf{F}_i $与$ \mathbf{F}_{ij} $之间的余弦相似度进行度量。在具有多视角不一致性的环境中，动态物体通常表现出较高的不确定性。

因此，我们将其形式化为如下相似性损失：

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777103122193-43c62a53-1f75-450d-850b-7dc5cabbce3c.png)

在这里，我们对每一对图像优化双向不确定性，以解耦帧间动态变化。

为了避免$ \mathbf{u}' \rightarrow +\infty $的平凡解，我们通过对数先验对不确定性进行正则化：

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777103194256-6b2314f4-3a47-46a5-9ca9-76040b1a99ad.png)

在这里，我们在不确定性项中加入一个偏置项$ 1.0 $，以防止先验损失为负。

因此，总的不确定性代价函数定义为：

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777103240026-eaf3b46d-b219-43df-b41e-23765b8ea7c4.png)

#### Uncertainty Regularization
<u>直接对逐像素不确定性进行优化可能会由于多种动态运动而导致空间不一致性以及对噪声的过拟合。为了解决这一问题，我们从 DINOv2 特征到不确定性之间学习一个局部仿射映射，并在其后接 Softplus 激活函数</u>。因此，不确定性通过$ \mathbf{u} = \text{Softplus}(\theta \cdot \mathbf{F}) $计算得到。该仿射映射在局部小窗口内起到正则化作用，这与以往方法 _[39, 66] _中的解码器结构有所不同。

> 其中$ \theta $为仿射变换$ \text{Softplus}() $的内部可优化参数。
>

#### Optimization
<u>为了避免对大规模 Hessian 矩阵进行求逆计算，我们采用带权重衰减的梯度下降（Gradient Descent with weight decay）来优化不确定性，而不是使用牛顿算法</u>。所有反向传播操作均在 CUDA 上实现，以保证计算效率。仿射映射层的可学习参数$ \theta $按如下雅可比形式进行更新：

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777103456429-5a030361-9e8b-4200-bcda-f85735ac55ee.png)

关于梯度推导的更多细节，请参见补充材料。

### SLAM System
<u>遵循 DROID-SLAM 的设置，我们累计具有足够运动信息的 12 个关键帧以初始化 SLAM 系统</u>。<u>DROID-SLAM 将视差初始化为常数</u>$ 1 $<u>，这在高动态场景中可能导致不准确的跟踪。因此，我们引入 Metric3D </u>_<u>[17]</u>_<u> 预测的度量单目深度</u>$ \mathbf{D}_t \in \mathcal{R}^{\frac{H}{8} \times \frac{W}{8}} $<u>，用于对视差进行约束，从而提高估计精度</u>。<u>因此，加入深度正则化后的 BA 代价函数定义如下</u>：

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777103576313-f9361a9a-7732-4e52-b0d4-ea540cbf65fc.png)

<u>在初始化之后，我们以增量方式处理新加入的关键帧</u>。<u>对于新加入的关键帧，我们遵循 DROID-SLAM 的策略，在滑动窗口内执行局部束调整（local bundle adjustment），并引入深度正则化</u>。<u>在初始化阶段与前端跟踪阶段，我们同时优化相机位姿、视差以及不确定性</u>。<u>在前端跟踪完成后，我们在所有关键帧上执行全局 BA，以进一步优化相机位姿与视差</u>。<u>在全局 BA 过程中，我们冻结动态不确定性参数，因为该仿射变换的设计初衷是在滑动窗口的局部范围内对不确定性进行正则化，而非在全局尺度上进行建模</u>。

## Experiments
**数据集**——<u>我们在 </u><u><font style="background-color:#F8B881;">Bonn RGBD Dynamic 数据集</font></u><u> </u>_<u>[38]</u>_<u>、</u><u><font style="background-color:#F8B881;">TUM RGB-D 数据集</font></u><u> </u>_<u>[46]</u>_<u> 以及 </u><u><font style="background-color:#F8B881;">DyCheck 数据集</font></u><u> </u>_<u>[11]</u>_<u> 上对所提出的方法进行评估</u>。为了进一步评估模型在无约束室外环境中的性能，我们引入了 DROID-W 数据集，该数据集使用固定安装在 RGB 相机上的 Livox Mid-360 激光雷达采集。该数据集包含 7 个序列（Downtown 1–7），RGB 图像分辨率为$ 1200 \times 1600 $，并提供真实相机位姿以及同步的 IMU 和 LiDAR 测量数据。由于 Downtown 1–2 无法获得基于卫星的定位信息，我们使用 FASTLIVO2 [65] 的轨迹作为真实值；其余序列则采用 RTK（实时动态差分定位）作为真值来源。

此外，我们还在从 YouTube 下载的 6 个动态视频上进行测试。这些序列时长从 8 秒到 30 分钟不等，涵盖了多种物体运动以及复杂的场景干扰。对于超过 5 分钟的视频，由于单 GPU 上 SLAM 运行的资源瓶颈，我们将其划分为不重叠的 5 分钟片段进行处理。对于每个视频，我们使用 MonST3R [62] 在 20 帧上估计相机内参。

**基线**——我们将方法与基于 SLAM 的方法以及近期的前向传播（feed-forward）方法进行对比。对于 SLAM 类方法，现有方法可以分为四类：  
(a) 经典 SLAM 方法：DSO _[10]_、ORB-SLAM2 _[34]_ 和 DROID-SLAM _[48]_；  
(b) 经典动态 SLAM 方法：ReFusion _[38]_ 和 DynaSLAM _[4]_；  
(c) 基于 NeRF / GS 的静态环境 SLAM 方法：NICE-SLAM _[70]_ 和 Splat-SLAM _[43]_；  
(d) 基于 NeRF / GS 的动态环境 SLAM 方法：DG-SLAM _[57]_、RoDyn-SLAM _[18]_、DDN-SLAM _[26]_、DynaMoN _[44]_、UP-SLAM _[67]_ 和 ADD-SLAM _[55]_。  
	对于前向传播方法，我们与 MonST3R _[62]_ 以及最新的 TTT3R _[7]_ 进行比较。

**指标**——我<u>们使用绝对轨迹误差（Absolute Trajectory Error, ATE）来评估相机跟踪精度</u>。对于 DyCheck 数据集 _[11]_，我们参考 MegaSaM _[28]_ 的做法，将真实相机轨迹归一化为单位长度，因为该数据集中序列长度差异较大。遵循 DROID-SLAM 的设置，我们的方法仅对关键帧进行优化。为了评估完整轨迹，我们通过$ SE(3) $插值恢复非关键帧的位姿，并随后进行位姿图更新（pose graph update）。对于所有方法，我们通过 Sim(3) Umeyama 对齐 _[50]_ 将估计的相机轨迹与真实轨迹进行配准。<u>除了跟踪精度外，我们还报告了平均运行时间，计算方式为输入帧数除以总运行时间</u>。

### Experimental Results
#### Quantitative Results
<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777103951013-d518ea00-8c8c-4a5d-b553-068f527199c8.png)

**表 1. 在 Bonn RGB-D Dynamic 数据集 [38] 上的跟踪性能（ATE RMSE ↓ [cm]）**。最佳结果分别以<font style="background-color:#8CCF17;">第一</font>、<font style="background-color:#C1E77E;">第二</font>、<font style="background-color:#FCE75A;">第三名</font>标出。“-”表示原论文未报告结果或无法获得代码。“F”表示跟踪失败。对于 MonST3R [62]，我们使用与本方法相同的关键帧设置，并采用窗口大小为 20、重叠率为 0.5 的滑动窗口方式进行评估，以降低内存消耗。

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777104058483-7402ba5d-0123-41ae-997e-9fb465cc6cce.png)

**表 2. 在 TUM RGB-D 数据集 [46] 上的跟踪性能（ATE RMSE ↓ [cm]）**。最佳结果分别以<font style="background-color:#8CCF17;">第一</font>、<font style="background-color:#C1E77E;">第二</font>、<font style="background-color:#FCE75A;">第三名</font>标出。“-”表示原论文未报告结果或无法获得代码。我们的方法在各序列上始终取得最优或次优结果，整体平均性能优于所有基线方法。

四个基准数据集上的相机跟踪结果分别汇报在_表 1_、_表 2_、_表 3_ 和_表 4_ 中。_<u>表 1</u>_<u> 表明，由于有效的不确定性优化，我们的方法在 Bonn RGB-D Dynamic 数据集 </u>_<u>[38]</u>_<u> 上相较所有基线方法均取得了最优的相机跟踪精度</u>。<u>如</u>_<u>表 2</u>_<u> 所示，WildGS-SLAM </u>_<u>[66]</u>_<u> 在低动态序列（f3/sr、f3/shs）上的表现相比 DROID-SLAM </u>_<u>[48]</u>_<u> 出现了明显下降</u>。这一差距主要源于不可靠的不确定性估计，而其根本原因是在视觉复杂环境下建图过程具有挑战性。相比之下，<u>我们的方法在低动态场景中能够达到与 DROID-SLAM 相当的跟踪精度，并在高动态序列上通过有效处理由运动引起的不一致性而显著优于 DROID-SLAM</u>。

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777104279179-79550238-c06f-4bfd-b5b3-c37a84cfe368.png)

**表 3. 在 DyCheck 数据集 [11] 上的跟踪性能（ATE RMSE ↓）**。最佳结果分别以<font style="background-color:#8CCF17;">第一</font>、<font style="background-color:#C1E77E;">第二</font>、<font style="background-color:#FCE75A;">第三名</font>标出。“-”表示原论文未报告结果或无法获得代码。“F”表示跟踪失败。我们的方法在高纹理、多样化环境中表现出良好的有效性与鲁棒性，而依赖目标分割或高斯建模进行不确定性优化的先前方法在此类场景中往往容易失效。

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777104365535-441249af-bffc-41a5-b432-febbbdedc131.png)

**表 4. 在 DROID-W 数据集上的跟踪性能（ATE RMSE ↓ [m]）**。最佳结果分别以<font style="background-color:#8CCF17;">第一</font>、<font style="background-color:#C1E77E;">第二名</font>标出。

<u>DyCheck 数据集在室内与室外场景中具有丰富的运动变化与场景多样性</u>。_<u>表 3</u>_<u> 表明，由于在复杂环境中场景重建困难以及不可靠的不确定性估计，WildGS-SLAM 往往无法实现准确的相机跟踪，而我们的方法在整体上保持了稳定性与准确性</u>。在 haru 场景中，一只移动的狗占据了主要视野，我们方法中精确的不确定性估计有效抑制了动态区域。然而，这也导致用于跟踪的可靠背景特征数量减少，从而在一定程度上降低了我们的性能。<u>总体而言，我们提出的方法在平均指标上优于所有基线方法</u>。_<u>表 4</u>_<u> 给出了我们提出的大规模室外数据集 DROID-W 上的实验结果。在这一极具挑战性的条件下，我们的方法相较于先前工作表现出更优的性能</u>。<u>相比之下，MonST3R </u>_<u>[62]</u>_<u> 和 TTT3R </u>_<u>[7]</u>_<u> 等前向传播方法在所有基准上都表现出明显更高的跟踪误差，显著劣于基于优化的 SLAM 系统</u>。

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777104474729-e85ec0f9-43f3-4e76-b78e-9d6db63928d2.png)

**表 5. 运行时间对比（平均 FPS ↑）**。所有实验均在 RTX 3090 GPU 与 16 核 CPU 的环境下进行评估。

<u>运行时间分析见</u>_<u>表 5</u>_<u>。我们与 DROID-SLAM 以及 WildGS-SLAM 进行对比，其中 WildGS-SLAM 是近期单目动态 SLAM 的最新最先进基线方法</u>。<u>我们的系统相较于 WildGS-SLAM 实现了约 40× 的加速，并能够以约 10 FPS 保持实时运行</u>。<u>由于引入了单目深度估计以及 DINOv2 </u>_<u>[37]</u>_<u> 特征提取，我们的方法在运行速度上略慢于 DROID-SLAM</u>。总体而言，这些结果表明，与现有基于 SLAM 的方法以及前向传播基线方法相比，我们提出的不确定性感知框架在有效性、鲁棒性与效率方面均具有明显优势。

#### Qualitative Comparisons
<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777104584928-97eb5cda-2ab6-4e00-858d-d0381e8b5068.png)

**图 3. 不确定性估计**。WildGS-SLAM [66] 与我们的方法对动态不确定性进行估计，而 MonST3R [62] 则预测二值运动掩码。相比之下，我们的方法在所有具有挑战性的序列上均能够生成更准确且空间一致性更强的不确定性估计结果。

_<u>图 3</u>_<u> 展示了不确定性图的对比结果。我们观察到，我们的方法能够提供最准确的动态不确定性估计</u>，而 <u>WildGS-SLAM 在运动物体附近产生了错误结果，并在复杂序列上出现严重的误判</u>。如_图 3_ 所示，TUM RGB-D 数据集包含运动模糊、局部过曝以及复杂的室内场景，这些因素很容易降低建图质量。我们引入的数据序列具有多样的物体运动与场景结构，对高质量几何重建提出了更高挑战。在这些低质量图像与高纹理背景的困难序列中，WildGS-SLAM 表现下降明显，错误的高斯重建进一步导致不稳定的不确定性估计。<u>MonST3R </u>_<u>[62]</u>_<u> 高度依赖于预训练模型所预测的动态点云对齐效果，由于其泛化能力有限，常常无法完整检测运动物体，甚至出现漏检情况</u>。

<u>相比之下，我们的方法能够生成空间一致性强且语义一致的不确定性图。在复杂场景中，它能够清晰地区分动态区域，同时在静态区域保持稳定的置信度，从而体现出我们不确定性优化方法的鲁棒性</u>。

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777104788535-f12f8452-2b3f-4910-b363-5556833af2ea.png)

**图 4. YouTube 序列上的三维重建对比**。我们比较了 DROID-SLAM [48]、WildGS-SLAM [66] 以及本方法的三维重建质量。其中，DROID-SLAM 与我们方法的点云结果直接进行可视化，而 WildGS-SLAM 的高斯渲染结果使用 3DGS 可视化工具展示。WildGS-SLAM 在大多数序列上均出现失败。DROID-SLAM 在复杂动态环境下表现出明显的尺度漂移（St. Moritz 1）、几何结构不准确（St. Moritz 3），以及噪声干扰（Tokyo Walking 2 与 3）。相比之下，我们的方法在高度动态且视觉复杂的真实场景中，能够生成更加准确且一致的三维重建结果。

<u>最后，我们在具有挑战性的 YouTube 序列上比较重建质量。如</u>_<u>图 4</u>_<u> 所示</u>，<u>DROID-SLAM 在动态场景中生成了不准确的点云，这是由于运动干扰导致重投影残差不可靠，从而破坏了位姿估计</u>。<u>DROID-SLAM 的重建结果在 St. Moritz 1 中表现出尺度漂移，在 St. Moritz 3 中出现错误几何结构，并在 Tokyo Walking 1 与 2 中产生大量噪声干扰</u>。在这些条件下，WildGS-SLAM 在高斯地图重建方面表现不佳，在所有序列上几乎均出现完全失败。相比之下，我们的方法能够生成几何上更准确且时间上更一致的点云，即使在具有挑战性的室外场景中，也能保持稳定的重建质量。

### Ablation Study
<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777104924181-e07e0f1b-d1d9-455a-90f9-377f4b486c61.png)

**表 6. 在 Bonn RGB-D 数据集 [38] 上的消融实验**。各配置的具体说明见第 4.2 节。

我们在_表 6_ 中对主要模块进行了消融实验。在 a.** **w/o Uncertainty-aware BA 设置中，我们关闭不确定性更新，仅使用置信度图对重投影项进行加权。对于实验 c.** **w/o uncertainty decouple，我们将_式 (6)_ 中的相似性损失修改如下：

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1777105034861-7b5d7f46-6ea9-4306-b363-f7ab42b4c140.png)

在实验 d. w/o affine mapping 中，不再通过优化仿射映射的参数来更新不确定性，而是直接对不确定性进行更新。移除仿射映射会在不确定性估计中引入时间与空间不一致性，从而导致性能下降。在实验 e. w/o weight decay 中，由于缺少对仿射映射的正则化项，系统会出现不稳定性，从而在部分场景中造成性能下降。<u>如</u>_<u>表 6</u>_<u> 所示，完整系统在所有变体中均取得了一致的最优表现，验证了各个模块设计的有效性</u>。

## Conclusion
本文提出了一种新颖的单目动态 SLAM 系统。该系统在可微分束调整框架中，利用多视角特征相似性对动态不确定性进行优化。大量实验表明，我们有效的不确定性优化方法能够在复杂真实场景中实现鲁棒的相机跟踪与精确的几何重建，而现有方法在这些场景中往往难以取得稳定表现。

**局限性（Limitations）**——我们的不确定性优化依赖于帧间对齐，因此在 SLAM 初始化阶段，由于位姿估计尚不可靠，可能会导致不确定性估计不准确。引入重建先验有望提升初始化阶段的鲁棒性。

