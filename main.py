import pyxel,  math

#Config
STAGE_WIDTH = 96
STAGE_HEIGHT = 192
STAGE_ROW = 12
STAGE_COLUMN = 6
STAGE_BG = (51, 51, 85)

SCORE_BG = (36, 208, 204)
FONT_HEIGHT = 8
FONT_LENGTH= 16

FREE_FALLING_SPEED = 8    #自由落下のスピード
ERASE_PUYO_COUNT = 4    #何個で消すか
PUYO_COLORS = 4    #何色使うか（１～５）
ERASE_ANIMATION_DURATION = 20    #点滅の長さ

PLAYER_FALLING_SPEED = 0.45    #操作中のぷよの自由落下速度
PLAYER_DOWN_SPEED = 7.5    #下を推しているときの落下速度
PLAYER_GROUND_FRAME = 10    #接地時間
PLAYER_MOVE_FRAME = 5    #移動時間
PLAYER_ROTATE_FRAME = 5     #回転時間

ZENKESHI_DURATION = 75    #全消し時のアニメーションミリセカンド
GAME_OVER_FRAME = 1500    #ゲームオーバー演出のサイクルフレーム


PUYO_IMG_WIDTH = STAGE_WIDTH // STAGE_COLUMN
PUYO_IMG_HEIGHT =  STAGE_HEIGHT // STAGE_ROW
        
class Puyo:
    def __init__(self, master, x, y, x_pos, y_pos, puyo, falling = False, destination = None, erasing = False):
        self.master = master
        self.x, self.y = x, y
        self.x_pos, self.y_pos = x_pos, y_pos
        self.puyo = puyo
        self.falling = falling
        self.destination = destination
        self.erasing = erasing
        self.vanish = False
        
        #以前追加されて、位置が重複しているぷよを削除
        tmp = master.puyo_list
        for puyo in tmp:
            if puyo.x_pos == self.x_pos and puyo.y_pos == self.y_pos:
                master.puyo_list.remove(puyo)
                del puyo
        
        master.puyo_list.append(self)
    def blit(self):
        if not self.vanish:
            pyxel.blt(self.x_pos, self.y_pos, 0, (self.puyo-1) * PUYO_IMG_WIDTH, 0, PUYO_IMG_WIDTH, PUYO_IMG_HEIGHT, 0)
        

class Stage:
    def __init__(self, master, width, height, row, column, bg):
        self.master = master
        self.bg = bg
        self.row, self.column = row, column
        self.width, self.height = width, height
        
        self.board = [
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0],
        ]
        
        self.falling_puyo_list = []
        self.erasing_puyo_info_list = []
        
        self.erase_start_frame = None
        self.zenkeshi_start_frame = None
        
        puyo_count = 0
        for y in range(self.row):
            line = self.board[y]
            for x in range(self.column):
                puyo = line[x] if x < len(line) else 0
                if 1 <= puyo <= 5:
                    self.set_puyo(x, y, puyo)
                    puyo_count += 1
                else:
                    line[x] = 0
        self.puyo_count = puyo_count
        
    def set_puyo(self, x, y, puyo):
        self.board[y][x] = puyo
    #自由落下をチェックする  
    def check_fall(self):
        self.falling_puyo_list = []
        is_falling = False
        #下の行から上の行を見ていく（1番下は除く）
        for y in range(self.row - 1)[::-1]:
            line = self.board[y]
            for x in range(self.column):
                if not line[x]:
                    #このマスにぷよがなければ次
                    continue
                if not self.board[y + 1][x]:
                    #このぷよは落ちるので取り除く
                    puyo = self.board[y][x]
                    self.board[y][x] = 0
                    dst = y
                    while dst + 1 < self.row and self.board[dst + 1][x] == 0:
                        dst += 1
                    #最終目的地に置く
                    self.board[dst][x] = puyo
                    #落ちるリストに入れる
                    tmp = Puyo(
                        master = self.master,
                        x = x, 
                        y = y, 
                        x_pos = x * PUYO_IMG_WIDTH,
                        y_pos = y * PUYO_IMG_HEIGHT,
                        puyo = puyo,
                        falling = True,
                        destination = dst * PUYO_IMG_HEIGHT
                        )
                    self.falling_puyo_list.append(tmp)
                    
                    #落ちるものがあったことを記録しておく
                    is_falling = True
        return is_falling
    
    def fall(self):
        is_falling = False
        for falling_puyo in self.falling_puyo_list:
            if not falling_puyo.falling:
                # 既に自由落下が終わっているので次
                continue
            position = falling_puyo.y_pos
            position += FREE_FALLING_SPEED
            if position >= falling_puyo.destination:
                # 自由落下終了
                position = falling_puyo.destination
                falling_puyo.falling = False
            else:
                # まだ落下しているぷよがあることを記録する
                is_falling = True
            # 新しい位置を保存する
            falling_puyo.y_pos = position
            
        return is_falling
    
    #消せるかどうか判定する
    def check_erase(self, start_frame):
        self.erase_start_frame = start_frame
        self.erasing_puyo_info_list = []
        # 何色のぷよを消したかを記録する
        erased_puyo_color = {}
        # 隣接ぷよを確認する関数内関数を作成
        sequence_puyo_info_list = []
        existing_puyo_info_list = []
        def check_sequential_puyo(x, y):
            # ぷよがあるか確認する
            orig = self.board[y][x]
            if not orig:
                #無いなら何もしない
                return
            # あるなら一旦退避して、メモリ上から消す
            puyo = self.board[y][x]
            tmp = Puyo(
                master = self.master,
                x = x,
                y = y,
                x_pos = x * PUYO_IMG_WIDTH,
                y_pos = y * PUYO_IMG_HEIGHT,
                puyo = puyo
            )
            sequence_puyo_info_list.append(tmp)
            self.board[y][x] = 0
            
            # 四方向の周囲ぷよを確認する
            direction = [[0, 1], [1, 0], [0, -1], [-1, 0]]
            for i in range(4):
                dx = x + direction[i][0]
                dy = y + direction[i][1]
                if dx < 0 or dy < 0 or dx >= self.column or dy >= self.row:
                    # ステージの外にはみ出た
                    continue
                cell = self.board[dy][dx]
                if not cell or cell != puyo:
                    # ぷよの色が違う
                    continue
                # そのぷよのまわりのぷよも消せるか確認する
                check_sequential_puyo(dx, dy)
        
        #実際に削除できるかの確認を行う
        for y in range(self.row):
            for x in range(self.column):
                sequence_puyo_info_list = []
                puyo_color = self.board[y][x]
                check_sequential_puyo(x, y)
                
                if len(sequence_puyo_info_list) == 0 or len(sequence_puyo_info_list) < ERASE_PUYO_COUNT:
                    # 連続して並んでいる数が足りなかったので消さない
                    if len(sequence_puyo_info_list):
                        # 退避していたぷよを消さないリストに追加する
                        existing_puyo_info_list.extend(sequence_puyo_info_list)
                        # 重複を無くす
                        tmp = []
                        for x in existing_puyo_info_list:
                            if x not in tmp:
                                tmp.append(x)
                        existing_puyo_info_list = tmp
                else:
                    #これらは消してよいので消すリストに追加する
                    self.erasing_puyo_info_list.extend(sequence_puyo_info_list)
                    # 重複を無くす
                    tmp = []
                    for x in self.erasing_puyo_info_list:
                        if x not in tmp:
                            tmp.append(x)
                    self.erasing_puyo_info_list = tmp
                    erased_puyo_color[puyo_color] = True
        self.puyo_count -=  len(self.erasing_puyo_info_list)
        #消さないリストに入っていたぷよをリストに復帰させる
        for info in existing_puyo_info_list:
            self.board[info.y][info.x] = info.puyo
        if self.erasing_puyo_info_list:
            # もし消せるならば、消えるぷよの個数と色の情報をまとめて返す
            return {
                "piece": len(self.erasing_puyo_info_list),
                "color": len(erased_puyo_color)
            }
        return None
    
    #消すアニメーションをする
    def erasing(self, frame):
        elapsed_frame = frame - self.erase_start_frame  
        ratio = elapsed_frame / ERASE_ANIMATION_DURATION
        if ratio > 1:
            # アニメーションを終了する
            tmp = list(self.erasing_puyo_info_list)
            for info in self.erasing_puyo_info_list:
                tmp.remove(info)
                self.master.puyo_list.remove(info)
                
            self.erasing_puyo_info_list = tmp
            return False
        elif ratio > 0.75:
            # 消えるぷよを表示する
            for info in self.erasing_puyo_info_list:
                info.vanish = False
            return True
        elif ratio > 0.5:
            # 消えるぷよを消す
            for info in self.erasing_puyo_info_list:
                info.vanish = True
            return True
        elif ratio > 0.25:
            # 消えるぷよを表示する
            for info in self.erasing_puyo_info_list:
                info.vanish = False
            return True
        else:
            # 消えるぷよを消す
            for info in self.erasing_puyo_info_list:
                info.vanish = True
            return True
    
    def update(self):
        pyxel.rect(0, 0, STAGE_WIDTH, STAGE_HEIGHT, 1)
        if self.zenkeshi_start_frame is not None:
            self.draw_zenkeshi(self.master.frame)
        for puyo in self.master.puyo_list:
            puyo.blit()
    
    def hide_zenkeshi(self):
        self.zenkeshi_start_frame = None
    def show_zenkeshi(self, frame):
        self.zenkeshi_start_frame = frame
    def draw_zenkeshi(self, frame):
        duration = frame - self.zenkeshi_start_frame
        ratio = min(duration / (ZENKESHI_DURATION//2), 1)
        y = (1 - ratio) * STAGE_HEIGHT
        pyxel.blt(0, y, 0, 0, 64, 96, 64, 0)
        if duration == ZENKESHI_DURATION:
            self.hide_zenkeshi()
    def batankyu(self, frame):
        ratio = (frame - GAME_OVER_FRAME) / GAME_OVER_FRAME
        x = math.cos(math.pi / 2 + ratio * math.pi * 2 * 10) * PUYO_IMG_WIDTH
        y = math.cos(math.pi + ratio * math.pi * 2) * PUYO_IMG_HEIGHT * STAGE_ROW / 4 + PUYO_IMG_HEIGHT * STAGE_ROW / 2
        pyxel.blt(x, y, 0, 0, 16, 96, 48, 0)
        
class Player:
    def __init__(self, master):
        self.master = master
        self.up = False
        self.down = False
        self.left = False
        self.right = False
        self.current = [pyxel.rndi(1, PUYO_COLORS), pyxel.rndi(1, PUYO_COLORS)]
        self.first = [pyxel.rndi(1, PUYO_COLORS), pyxel.rndi(1, PUYO_COLORS)]
        self.second = [pyxel.rndi(1, PUYO_COLORS), pyxel.rndi(1, PUYO_COLORS)]
    #ぷよ設置確認
    def create_new_puyo(self):
        # ぷよぷよが置けるかどうか、1番上の段の左から3つ目を確認する
        if self.master.stage.board[0][2]:
            # 空白でない場合は新しいぷよを置けない
            return False
        # 新しいぷよの色を決める
        self.current = self.first
        self.first = self.second
        self.second = [pyxel.rndi(1, PUYO_COLORS), pyxel.rndi(1, PUYO_COLORS)]
        self.center_puyo = self.current[0]
        self.movable_puyo = self.current[1]
        
        #ぷよの初期位置を定める
        self.x, self.y  = 2, -1
        self.dx, self.dy = 0, -1    #動くぷよの相対位置
        self.rotation = 90    #動くぷよの角度は90度（上向き）
        
        # 新しいぷよを作成する
        self.center_puyo_element = Puyo(
            master = self.master,
            x = self.x,
            y = self.y,
            x_pos = self.x * PUYO_IMG_WIDTH,
            y_pos = self.y * PUYO_IMG_HEIGHT,
            puyo = self.center_puyo
        )
        self.movable_puyo_element = Puyo(
            master = self.master,
            x = self.x + self.dx,
            y = self.y + self.dy,
            x_pos = (self.x + self.dx) * PUYO_IMG_WIDTH,
            y_pos = (self.y + self.dy) * PUYO_IMG_HEIGHT,
            puyo = self.movable_puyo
        )
        
        #接地時間はゼロ
        self.ground_frame = 0
        #ぷよを描画
        self.set_puyo_position()
        return True 
    
    def set_puyo_position(self):
        self.center_puyo_element.x = self.x
        self.center_puyo_element.y = self.y
        x = self.x + math.cos(self.rotation * math.pi / 180) * PUYO_IMG_WIDTH
        y = self.y - math.sin(self.rotation * math.pi / 180) * PUYO_IMG_HEIGHT
        self.movable_puyo_element.x = x
        self.movable_puyo_element.y = y
    
    def falling(self, is_down_pressed):
        # 現状の場所の下にブロックがあるかどうか確認する
        is_blocked = False
        x = self.x
        y = self.y

        dx = self.dx
        dy = self.dy
        if y + 1 >= STAGE_ROW or self.master.stage.board[y + 1][x] or (y + dy + 1 >= 0 and (y + dy + 1 >= STAGE_ROW or self.master.stage.board[y + dy + 1][x + dx])):
            is_blocked = True
        if not is_blocked:
            # 下にブロックがないなら自由落下してよい。プレイヤー操作中の自由落下処理をする
            self.center_puyo_element.y_pos += PLAYER_FALLING_SPEED
            self.movable_puyo_element.y_pos += PLAYER_FALLING_SPEED
            if is_down_pressed:
                # 下キーが押されているならもっと加速する
                self.center_puyo_element.y_pos += PLAYER_DOWN_SPEED
                self.movable_puyo_element.y_pos += PLAYER_DOWN_SPEED
            if self.center_puyo_element.y_pos // PUYO_IMG_HEIGHT != self.center_puyo_element.y:
                #ブロックの境を超えたので再チェックする
                #下キーが押されていたら、得点を加算する
                if is_down_pressed:
                    self.master.score.add_score(1)
                y += 1
                self.y = y
                self.center_puyo_element.y = y
                self.center_puyo_element.y_pos = y * PUYO_IMG_HEIGHT
                self.movable_puyo_element.y_pos = (y + dy) * PUYO_IMG_HEIGHT
                if y + 1 >= STAGE_ROW or self.master.stage.board[y + 1][x] or (y + dy + 1 >= 0 and (y + dy + 1 >= STAGE_ROW or self.master.stage.board[y + dy + 1][x + dx])):
                    is_blocked = True
                if not is_blocked:
                    # 境を超えたが特に問題はなかった。次回も自由落下を続ける
                    self.ground_frame = 0
                    return
                else:
                    # 境を超えたらブロックにぶつかった。位置を調節して、接地を開始する
                    self.center_puyo_element.y_pos = y * PUYO_IMG_HEIGHT
                    self.ground_frame = 1
                    return
            else:
                #自由落下で特に問題がなかった。次回も自由落下を続ける
                self.ground_frame = 0
                return
        if self.ground_frame == 0:
            #初接地である。接地を開始する
            self.ground_frame = 1
            return
        else:
            self.ground_frame += 1
            if self.ground_frame >= PLAYER_GROUND_FRAME:
                return True
            
    def playing(self, frame):
        # まず自由落下を確認する
        # 下キーが押されていた場合、それ込みで自由落下させる
        if self.falling(self.down):
            # 落下が終わっていたら、ぷよを固定する
            self.set_puyo_position()
            return 'fix'
        self.set_puyo_position()
        if self.right or self.left:
            #左右の確認をする
            cx = self.right if self.right else -1
            x = self.x
            y = self.y
            mx = x + self.dx
            my = y + self.dy
            # その方向にブロックがないことを確認する
            # まずは自分の左右を確認
            can_move = True
            if y < 0 or x + cx < 0 or x + cx >= STAGE_COLUMN or self.master.stage.board[y][x + cx]:
                if y >= 0:
                    can_move = False
            if my < 0 or mx + cx < 0 or mx + cx >= STAGE_COLUMN or self.master.stage.board[my][mx + cx]:
                if my >= 0:
                    can_move = False
            # 接地していない場合は、さらに1個下のブロックの左右も確認する
            if self.ground_frame == 0:
                if y + 1 < 0 or x + cx < 0 or x + cx >= STAGE_COLUMN or self.master.stage.board[y + 1][x + cx]:
                    if y + 1 >= 0:
                        can_move = False
                if my + 1 < 0 or mx + cx < 0 or mx + cx >= STAGE_COLUMN or self.master.stage.board[my + 1][mx + cx]:
                    if my + 1 >= 0:
                        can_move = False
            if can_move:       
                # 動かすことが出来るので、移動先情報をセットして移動状態にする   
                self.action_start_frame = frame
                self.move_source = x * PUYO_IMG_WIDTH
                self.move_destination = (x + cx) * PUYO_IMG_WIDTH
                self.x += cx
                return 'moving'
        elif self.up:
            #回転を確認する
            # 回せるかどうかは後で確認。まわすぞ
            x = self.x
            y = self.y
            mx = x + self.dx
            my = y + self.dy
            rotation = self.rotation
            can_rotate = True
            
            cx = 0
            cy = 0
            if rotation == 0:
                # 右から上には100% 確実に回せる。何もしない
                pass
            elif rotation == 90:
                # 上から左に回すときに、左にブロックがあれば右に移動する必要があるのでまず確認する
                if y + 1 < 0 or x - 1 < 0 or x - 1 >= STAGE_COLUMN or self.master.stage.board[y + 1][x - 1]:
                    if y + 1 >= 0:
                        # ブロックがある。右に1個ずれる
                        cx = 1
                #右にずれる必要があるとき、右にもブロックがあれば回転出来ないので確認する
                if cx == 1:
                    if y + 1 < 0 or x + 1 < 0 or y + 1 >= STAGE_ROW or x + 1 >= STAGE_COLUMN or self.master.stage.board[y + 1][x + 1]:
                        if y + 1 >= 0:
                            # ブロックがある。回転出来なかった
                            can_rotate = False
            elif rotation == 180:
                # 左から下に回す時には、自分の下か左下にブロックがあれば1個上に引き上げる。まず下を確認する
                    if y + 2 < 0 or y + 2 >= STAGE_ROW or self.master.stage.board[y + 2][x]:
                        if y + 2 >= 0:
                            # ブロックがある。上に引き上げる
                            cy = -1
                    # 左下も確認する
                    if y + 2 < 0 or y + 2 >= STAGE_ROW or x - 1 < 0 or self.master.stage.board[y + 2][x - 1]:
                        if y + 2 >= 0:
                            # ブロックがある。上に引き上げる
                            cy = -1
            elif rotation == 270:
                # 下から右に回すときは、右にブロックがあれば左に移動する必要があるのでまず確認する
                if y + 1 < 0 or x + 1 < 0 or x + 1 >= STAGE_COLUMN or self.master.stage.board[y + 1][x + 1]:
                    if y + 1 >= 0:
                        # ブロックがある。左に1個ずれる
                        cx = -1
                #左にずれる必要があるとき、左にもブロックがあれば回転できないので確認する
                if cx == -1:
                    if y + 1 < 0 or x - 1 < 0 or x - 1 >= STAGE_COLUMN or self.master.stage.board[y + 1][x - 1]:
                        if y + 1 >= 0:
                            # ブロックがある。回転出来なかった
                            can_rotate = False
            if can_rotate:
                #上に移動する必要があるときは、一気に上げてしまう
                if cy == -1:
                    self.y -= 1
                        
                    self.ground_frame = 0
                    self.center_puyo_element.y = self.y * PUYO_IMG_HEIGHT
                    
                #回すことが出来るので、回転後の情報をセットして回転状態にする
                self.action_start_frame = frame
                self.rotate_before_left = x * PUYO_IMG_HEIGHT
                self.rotate_after_left = (x + cx) * PUYO_IMG_HEIGHT
                self.rotate_from_rotation = self.rotation
                #次の状態を先に設定しておく
                self.x += cx
                dist_rotation = (self.rotation + 90) % 360
                d_combi = [[1, 0], [0, -1], [-1, 0], [0, 1]][dist_rotation // 90]
                self.dx = d_combi[0]
                self.dy = d_combi[1]
                return 'rotating'
        return 'playing'
    
    def moving(self, frame):
        # 移動中も自然落下はさせる
        self.falling(self.down)
        ratio = min(1, (frame - self.action_start_frame) / PLAYER_MOVE_FRAME)
        tmp = self.center_puyo_element.x_pos
        self.center_puyo_element.x_pos = ratio * (self.move_destination - self.move_source) + self.move_source
        diff = self.center_puyo_element.x_pos - tmp
        self.movable_puyo_element.x_pos += diff
        self.set_puyo_position()
        if ratio == 1:
            return False
        return True
    
    def rotating(self, frame):
        # 回転中も自然落下はさせる
        self.falling(self.down)
        ratio = min(1, (frame - self.action_start_frame) / PLAYER_ROTATE_FRAME)
        self.center_puyo_element.x_pos = (self.rotate_after_left - self.rotate_before_left) * ratio + self.rotate_before_left
        self.rotation = self.rotate_from_rotation + ratio * 90
        self.movable_puyo_element.x_pos = self.center_puyo_element.x_pos + math.cos(self.rotation * math.pi/180) * PUYO_IMG_WIDTH
        self.movable_puyo_element.y_pos = self.center_puyo_element.y_pos + math.sin((self.rotation + 180) * math.pi/180) * PUYO_IMG_HEIGHT
        self.set_puyo_position()
        if ratio == 1:
            self.rotation = (self.rotate_from_rotation + 90) % 360
            return False
        return True
    
    def fix(self):
        # 現在のぷよをステージ上に配置する
        x = self.x
        y = self.y
        dx = self.dx
        dy = self.dy
    
        if y >= 0:
            # 画面外のぷよは消してしまう
            self.master.stage.set_puyo(x, y, self.center_puyo)
            self.master.stage.puyo_count += 1

        if y + dy >= 0:
            # 画面外のぷよは消してしまう
            self.master.stage.set_puyo(x + dx, y + dy, self.movable_puyo)
            self.master.stage.puyo_count += 1
        
        #操作用に作成したぷよ画像を消す
        self.master.puyo_list.remove(self.center_puyo_element)
        self.master.puyo_list.remove(self.movable_puyo_element)
    
    def batankyu(self):
        if self.up:
            self.master.start()
            
            
class Score:
    rensa_bonus = [0, 8, 16, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448, 480, 512, 544, 576, 608, 640, 672]
    piece_bonus = [0, 0, 0, 0, 2, 3, 4, 5, 6, 7, 10, 10]
    color_bonus = [0, 0, 3, 6, 12, 24]
    
    def __init__(self, master):
        self.score = 0   
        
    def show_score(self):
        score = self.score
        nums = []

        # スコアを下の桁から埋めていく
        for i in range(FONT_LENGTH):
            # 10で割ったあまりを求めて、一番下の桁を取り出す
            number = score % 10
            # 一番うしろに追加するのではなく、一番前に追加することで、スコアの並びを数字と同じようにする
            nums.insert(0, number)
            # 10 で割って次の桁の準備をしておく
            score = score // 10
            
        for i, n in enumerate(nums):
            pyxel.blt(i * (STAGE_WIDTH//FONT_LENGTH), STAGE_HEIGHT, 0, n*6, 128, 6, 8, 0)
            

    def calculate_score(self, rensa, piece, color):
        rensa = min(rensa, len(Score.rensa_bonus) - 1)
        piece = min(piece, len(Score.piece_bonus) - 1)
        color = min(color, len(Score.color_bonus) - 1)
        scale = Score.rensa_bonus[rensa] + Score.piece_bonus[piece] + Score.color_bonus[color]
        if scale == 0:
            scale = 1
        self.add_score(scale * piece * 10)

    def add_score(self, score):
        self.score += score
        self.show_score()
            
            
class Main:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.start()
        
    def start(self):
        self.mode = 'start'
        self.frame = 0
        self.combination_count = 0
        self.puyo_list = []
        
        self.stage = Stage(self, STAGE_WIDTH, STAGE_HEIGHT, STAGE_ROW, STAGE_COLUMN, STAGE_BG)
        self.player = Player(self)
        self.score = Score(self)
        
    def loop(self):
        self.stage.update()
        if self.mode == 'start':
            # 最初は、もしかしたら空中にあるかもしれないぷよを自由落下させるところからスタート
            self.mode = 'checkFall'

        elif self.mode == 'checkFall':
            # 落ちるかどうか判定する
            if self.stage.check_fall():
                self.mode = 'fall'
            else:
                # 落ちないならば、ぷよを消せるかどうか判定する
                self.mode = 'checkErase'

        elif self.mode == 'fall':
            if not self.stage.fall():
                # すべて落ちきったら、ぷよを消せるかどうか判定する
                self.mode = 'checkErase'

        elif self.mode == 'checkErase':
            # 消せるかどうか判定する
            eraseInfo = self.stage.check_erase(self.frame)
            if eraseInfo:
                self.mode = 'erasing'
                self.combination_count += 1
                # 得点を計算する
                self.score.calculate_score(self.combination_count, eraseInfo['piece'], eraseInfo['color'])
                self.stage.hide_zenkeshi()
            else:
                if self.stage.puyo_count == 0 and self.combination_count > 0:
                    # 全消しの処理をする
                    self.stage.show_zenkeshi(self.frame)
                    self.score.add_score(3600)
                    pass
                self.combination_count = 0
                # 消せなかったら、新しいぷよを登場させる
                self.mode = 'newPuyo'

        elif self.mode == 'erasing':
            if not self.stage.erasing(self.frame):
                # 消し終わったら、再度落ちるかどうか判定する
                self.mode = 'checkFall'

        elif self.mode == 'newPuyo':
            if not self.player.create_new_puyo():
                # 新しい操作用ぷよを作成出来なかったら、ゲームオーバー
                self.mode = 'gameOver'
            else:
                # プレイヤーが操作可能
                self.mode = 'playing'

        elif self.mode == 'playing':
            # プレイヤーが操作する
            action = self.player.playing(self.frame)
            self.mode = action # 'playing', 'moving', 'rotating', 'fix' のどれかが帰ってくる

        elif self.mode == 'moving':
            if not self.player.moving(self.frame):
                # 移動が終わったので操作可能にする
               self.mode = 'playing'

        elif self.mode == 'rotating':
            if not self.player.rotating(self.frame):
                # 回転が終わったので操作可能にする
                self.mode = 'playing'

        elif self.mode == 'fix':
            # 現在の位置でぷよを固定する
            self.player.fix()
            # 固定したら、まず自由落下を確認する
            self.mode = 'checkFall'

        elif self.mode == 'gameOver':
            # ばたんきゅーの準備をする
            #puyo_image.prepare_batankyu(self.frame)
            self.mode = 'batankyu'

        elif self.mode == 'batankyu':
            self.player.batankyu()

        self.frame += 1
    def blit(self):
        pyxel.rect(self.x, self.y + STAGE_HEIGHT, STAGE_WIDTH, FONT_HEIGHT, 12)
        self.score.show_score()
        self.stage.update()
        if self.mode == 'batankyu':
            self.stage.batankyu(self.frame)
        pyxel.rect(self.x +  STAGE_WIDTH, self.y, PUYO_IMG_WIDTH,  PUYO_IMG_HEIGHT*2, 0)
        pyxel.blt(self.x + STAGE_WIDTH, self.y + PUYO_IMG_HEIGHT, 0, (self.player.first[0] - 1) * PUYO_IMG_WIDTH, 0, PUYO_IMG_WIDTH, PUYO_IMG_HEIGHT, 0)
        pyxel.blt(self.x + STAGE_WIDTH, self.y, 0, (self.player.first[1]-1) * PUYO_IMG_WIDTH, 0, PUYO_IMG_WIDTH, PUYO_IMG_HEIGHT, 0)
        
        pyxel.rect(self.x +  STAGE_WIDTH + PUYO_IMG_WIDTH, self.y + PUYO_IMG_HEIGHT * 2, PUYO_IMG_WIDTH,  PUYO_IMG_HEIGHT*2, 0)   
        pyxel.blt(self.x + STAGE_WIDTH + PUYO_IMG_WIDTH, self.y + PUYO_IMG_HEIGHT*3, 0, (self.player.second[0] - 1) * PUYO_IMG_WIDTH, 0, PUYO_IMG_WIDTH, PUYO_IMG_HEIGHT, 0)
        pyxel.blt(self.x + STAGE_WIDTH + PUYO_IMG_WIDTH, self.y + PUYO_IMG_HEIGHT*2, 0, (self.player.second[1]-1) * PUYO_IMG_WIDTH, 0, PUYO_IMG_WIDTH, PUYO_IMG_HEIGHT, 0)

class App:
    def __init__(self):
        global player1
        pyxel.init(int(STAGE_WIDTH*1.5), STAGE_HEIGHT + FONT_HEIGHT, fps = 30)
        player1 = Main(0, 0)
        pyxel.load('puyo.pyxres')
        pyxel.run(self.update, self.draw)
        
    def update(self):
        player1.loop()
        player1.player.left = player1.player.right = player1.player.up = player1.player.down = False
        if pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_LEFT):
            player1.player.left = True
        elif pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT):
            player1.player.right = True
        elif pyxel.btn(pyxel.KEY_UP) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_B):
            player1.player.up = True
        elif pyxel.btn(pyxel.KEY_DOWN) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN):
            player1.player.down = True
        
    def draw(self):
        pyxel.cls(12)
        player1.blit()
        
if __name__ == '__main__':
    App()
