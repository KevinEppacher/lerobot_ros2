import os
import tempfile

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, RegisterEventHandler
from launch.conditions import IfCondition
from launch.event_handlers import OnShutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from moveit_configs_utils import MoveItConfigsBuilder


def launch_setup(context):
    dof = LaunchConfiguration('dof').perform(context)
    namespace = LaunchConfiguration('namespace').perform(context)

    if not namespace or '/' in namespace:
        raise ValueError('namespace must be a non-empty ROS namespace segment')

    prefix = f'{namespace}_'
    package_share = get_package_share_directory('lerobot_moveit_config')
    description_share = get_package_share_directory('so101_description')

    config = (
        MoveItConfigsBuilder(
            f'so101_{dof}dof',
            package_name='lerobot_moveit_config',
        )
        .robot_description(
            file_path=os.path.join(
                description_share,
                'urdf',
                'robots',
                f'so101_{dof}dof.urdf.xacro',
            ),
            mappings={'prefix': prefix},
        )
        .robot_description_semantic(
            file_path=f'config/{dof}dof/so101.srdf',
            mappings={'prefix': prefix},
        )
        .robot_description_kinematics(
            file_path=f'config/{dof}dof/kinematics.yaml',
        )
        .joint_limits(
            file_path='config/common/joint_limits.yaml',
        )
        .planning_pipelines(
            pipelines=['ompl'],
            default_planning_pipeline='ompl',
        )
        .trajectory_execution(
            file_path='config/common/moveit_controllers.yaml',
            moveit_manage_controllers=True,
        )
        .to_moveit_configs()
    )

    ompl_config_path = os.path.join(
        package_share,
        'config',
        'common',
        'ompl_planning.yaml',
    )

    with open(ompl_config_path, encoding='utf-8') as file:
        config.planning_pipelines['ompl'] = yaml.safe_load(file)

    parameters = config.to_dict()
    parameters['ros_control_namespace'] = f'/{namespace}'

    move_group = Node(
        package='moveit_ros_move_group',
        executable='move_group',
        namespace=namespace,
        parameters=[parameters],
        emulate_tty=True,
        output='screen',
    )

    # Load the RViz configuration template.
    rviz_config_path = os.path.join(
        package_share,
        'rviz',
        'moveit.rviz',
    )

    with open(rviz_config_path, encoding='utf-8') as file:
        rviz_config = file.read()

    # Replace the MoveGroup namespace placeholder.
    rviz_config = rviz_config.replace(
        '__MOVE_GROUP_NAMESPACE__',
        f'/{namespace}',
    )

    # Create a temporary RViz configuration.
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.rviz',
        prefix=f'moveit_{namespace}_',
        delete=False,
        encoding='utf-8',
    ) as file:
        file.write(rviz_config)
        generated_rviz_config = file.name

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        namespace=namespace,
        output='screen',
        arguments=[
            '-d',
            generated_rviz_config,
            '-f',
            f'{prefix}base_link',
        ],
        parameters=[parameters],
        condition=IfCondition(LaunchConfiguration('gui')),
    )

    # Remove the temporary RViz configuration on shutdown.
    def cleanup_rviz_config(event, context):
        if os.path.exists(generated_rviz_config):
            os.unlink(generated_rviz_config)

    cleanup = RegisterEventHandler(
        OnShutdown(
            on_shutdown=cleanup_rviz_config,
        )
    )

    return [
        move_group,
        rviz,
        cleanup,
    ]

def generate_launch_description():
    ld = LaunchDescription()
    ld.add_action(DeclareLaunchArgument('dof', default_value='5', choices=['5', '6']))
    ld.add_action(DeclareLaunchArgument('namespace', default_value='follower'))
    ld.add_action(DeclareLaunchArgument('gui', default_value='true'))
    ld.add_action(OpaqueFunction(function=launch_setup))
    return ld
