
/**
 * PlayerManager を実装するクラスは、プレイヤーに紐づく様々な機能のロジックを提供し、各機能に責任を持つ
 */
abstract class PlayerManager {
    public abstract init(): Promise<void>;
    public abstract destroy(): Promise<void>;
}

export default PlayerManager;
