
/**
 * PlayerManager を実装するクラスは、PlayerController に紐づく様々な機能のロジックを提供し、各機能に責任を持つ
 */
abstract class PlayerManager {

    /**
     * ユーザー操作により DPlayer 側で画質が切り替わった際、この PlayerManager の再起動が必要かどうかを PlayerController に示す値
     * この値が true の場合、PlayerController は画質切り替えが開始されたタイミングでこの PlayerManager を破棄し、再度 init() を実行する
     * LiveDataBroadcastingManager など、実装上画質切り替え後にそのまま対応できない PlayerManager はこの値を true に設定すべき
     */
    public abstract readonly restart_required_when_quality_switched: boolean;

    /**
     * PlayerController に紐づく様々な機能のロジックを初期化する
     * コンストラクタでは引数の受け取りとプロパティの初期化など、最低限の処理のみを行う
     * 任意のタイミングで再初期化できるよう、destroy() で破棄した後もう一度 init() を実行すれば再度初期化できる実装にすべき
     */
    public abstract init(): Promise<void>;

    /**
     * PlayerController に紐づく様々な機能のロジックを破棄する
     * 破棄後に init() を実行して再初期化できるように、利用したリソースをすべて適切に破棄する実装にすべき
     */
    public abstract destroy(): Promise<void>;
}

export default PlayerManager;
