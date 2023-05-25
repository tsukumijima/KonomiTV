
/**
 * PlayerManager を実装するクラスは、プレイヤーに紐づく様々な機能のロジックを提供し、各機能に責任を持つ
 */
abstract class PlayerManager {

    /**
     * プレイヤーに紐づく様々な機能のロジックを初期化する
     * コンストラクタでは引数の受け取りとプロパティの初期化など最低限の処理のみを行う
     * destroy() で破棄した後もう一度 init() を実行すれば再度初期化できる実装にすべき
     */
    public abstract init(): Promise<void>;

    /**
     * プレイヤーに紐づく様々な機能のロジックを破棄する
     * 破棄後に init() を実行して再初期化できるように、利用したリソースをすべて適切に破棄する実装にすべき
     */
    public abstract destroy(): Promise<void>;
}

export default PlayerManager;
