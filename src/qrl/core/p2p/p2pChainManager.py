from pyqrllib.pyqrllib import bin2hstr
from pyqryptonight.pyqryptonight import UInt256ToString

from qrl.core.misc import logger
from qrl.core.Block import Block
from qrl.core.p2p.p2pObserver import P2PBaseObserver
from qrl.generated import qrllegacy_pb2, qrl_pb2


class P2PChainManager(P2PBaseObserver):
    """
    P2PChainManager is a collection of function handlers that will be called
    whenever P2P messages that have to do with blocks arrive. Such messages are
    'fetch block', 'request block height', 'request headerhashes', 'block
    received', and are defined in qrllegacy.proto:LegacyMessage.
    """
    def __init__(self):
        super().__init__()

    def new_channel(self, channel):
        channel.register(qrllegacy_pb2.LegacyMessage.BK, self.handle_block)
        channel.register(qrllegacy_pb2.LegacyMessage.FB, self.handle_fetch_block)
        channel.register(qrllegacy_pb2.LegacyMessage.PB, self.handle_push_block)
        channel.register(qrllegacy_pb2.LegacyMessage.BH, self.handle_block_height)
        channel.register(qrllegacy_pb2.LegacyMessage.HEADERHASHES, self.handle_node_headerhash)

    def handle_fetch_block(self, source, message: qrllegacy_pb2.LegacyMessage):  # Fetch Request for block
        """
        This function responds to a fetch_block request comes in from a peer
        node by sending the block.
        :return:
        """
        P2PBaseObserver._validate_message(message, qrllegacy_pb2.LegacyMessage.FB)

        block_number = message.fbData.index

        logger.info(' Request for %s by %s', block_number, source.peer)
        if 0 < block_number <= source.factory.chain_height:
            block = source.factory.get_block_by_number(block_number)
            msg = qrllegacy_pb2.LegacyMessage(func_name=qrllegacy_pb2.LegacyMessage.PB,
                                              pbData=qrllegacy_pb2.PBData(block=block.pbdata))
            source.send(msg)

    def handle_push_block(self, source, message: qrllegacy_pb2.LegacyMessage):
        """
        This function processes requested blocks received while syncing.
        Block received under this function are directly added to the main
        chain i.e. chain.blockchain
        It expects to receive only one block for a given blocknumber.
        :return:
        """
        # FIXME: Later rename
        P2PBaseObserver._validate_message(message, qrllegacy_pb2.LegacyMessage.PB)
        if message.pbData is None:
            return

        try:
            block = Block(message.pbData.block)
            source.factory.block_received(source, block)

        except Exception as e:
            logger.error('block rejected - unable to decode serialised data %s', source.peer)
            logger.exception(e)

    def handle_block(self, source, message: qrllegacy_pb2.LegacyMessage):  # block received
        """
        Block
        This function processes any new block received.
        :return:
        """
        P2PBaseObserver._validate_message(message, qrllegacy_pb2.LegacyMessage.BK)
        try:
            block = Block(message.block)
        except Exception as e:
            logger.error('block rejected - unable to decode serialised data %s', source.peer)
            logger.exception(e)
            return

        logger.info('>>>Received block from %s %s %s',
                    source.peer.full_address,
                    block.block_number,
                    bin2hstr(block.headerhash))

        if not source.factory.master_mr.isRequested(block.headerhash, source, block):
            return

        source.factory.pow.pre_block_logic(block)  # FIXME: Ignores return value
        source.factory.master_mr.register(qrllegacy_pb2.LegacyMessage.BK, block.headerhash, message.block)

    def handle_block_height(self, source, message: qrllegacy_pb2.LegacyMessage):
        """
        Updates the node's database of which peer is at which blockheight when a
        peer reports its blockheight
        :return:
        """
        if message.bhData.block_number == 0:
            block = source.factory.last_block
            cumulative_difficulty = source.factory.get_cumulative_difficulty()
            if block.block_number == 0:
                return
            bhdata = qrl_pb2.BlockHeightData(block_number=block.block_number,
                                             block_headerhash=block.headerhash,
                                             cumulative_difficulty=bytes(cumulative_difficulty))
            msg = qrllegacy_pb2.LegacyMessage(func_name=qrllegacy_pb2.LegacyMessage.BH,
                                              bhData=bhdata)
            source.send(msg)
            return

        try:
            UInt256ToString(message.bhData.cumulative_difficulty)
        except ValueError:
            logger.warning('Invalid Block Height Data')
            source.loseConnection()
            return

        source.factory.update_peer_blockheight(source.peer.full_address,
                                               message.bhData.block_number,
                                               message.bhData.block_headerhash,
                                               message.bhData.cumulative_difficulty)

    def handle_node_headerhash(self, source, message: qrllegacy_pb2.LegacyMessage):
        """
        If the peer sent a node_headerhash message with length=0, this means the
        peer is requesting this node's headerhashes. Otherwise, compare our
        headerhashes and synchronize with peer if necessary.
        :return:
        """

        if len(message.nodeHeaderHash.headerhashes) == 0:
            node_headerhash = source.factory.get_headerhashes(message.nodeHeaderHash.block_number)
            msg = qrllegacy_pb2.LegacyMessage(func_name=qrllegacy_pb2.LegacyMessage.HEADERHASHES,
                                              nodeHeaderHash=node_headerhash)
            source.send(msg)
        else:
            source.factory.compare_and_sync(source, message.nodeHeaderHash)
