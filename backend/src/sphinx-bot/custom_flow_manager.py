from pipecat_flows.manager import FlowManager
from status_utils import status_updater  # Assuming this is your status update utility
from loguru import logger

class CustomFlowManager(FlowManager):
    async def set_node(self, node_name, node_config):
        # Call the parent class's set_node to maintain default behavior
        await super().set_node(node_name, node_config)
        
        logger.info(f"Node {node_name} state: {self.state}")
        # Initialize emotion-related states if not present
        if not hasattr(self, 'state'):
            self.state = {}
        self.state.setdefault('user_started_speaking', False)
        self.state.setdefault('emotions_fully_processed', False)

        # Check if the node config includes a ui_override
        if "ui_override" in node_config:
            # Send the ui_override message via your status_updater
            await status_updater.update_status(
                f"Stage {node_name} active",
                {"node": node_name},
                ui_override=node_config["ui_override"]
            )
        else:
            # Optionally send a default status update without ui_override
            await status_updater.update_status(
                f"Stage {node_name} active",
                {"node": node_name}
            )

        #hack
        if node_name=="goodbye":
            logger.info("Goodbye node reached")
            if "empowered_state" in self.state and self.state["empowered_state"]:
                logger.info("Empowered state detected: {}".format(self.state["empowered_state"]))
                
                empowered_state = self.state["empowered_state"]
                combined_emotions = self.state.get("combined_emotions", None)
                challenge = self.state.get("challenge", None)
                
                await status_updater.trigger_video(
                    f"Empowered state detected : {empowered_state}",
                    {"empowered_state" : empowered_state,
                    "combined_emotions" : combined_emotions,
                    "challenge" : challenge}
                )