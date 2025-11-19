#include <iostream>
#include <sstream>
#include <random>
#include <vector>

using namespace std;

#define int long long

struct Treap {
  struct Node {
      int count;
      int priority;
      int idx_left_child;
      int idx_right_child;
      int val;
      bool reversed = 0; 
      int subtree_min; 
      int lazy_add = 0; 
  };

  int Gen() { 
      static std::mt19937 Generator(42);
      return std::uniform_int_distribution<int>()(Generator);
  }

  int get_cnt(int idx_v) {
      return (idx_v == -1) ? 0 : tree[idx_v].count;
  }


  void push(int idx_v) {
    if (idx_v == -1) return;
    if (tree[idx_v].lazy_add != 0) {
      tree[idx_v].val += tree[idx_v].lazy_add;
      tree[idx_v].subtree_min += tree[idx_v].lazy_add;

      if (tree[idx_v].idx_left_child != -1) {
      tree[tree[idx_v].idx_left_child].lazy_add += tree[idx_v].lazy_add;

      }
      if (tree[idx_v].idx_right_child != -1){
      tree[tree[idx_v].idx_right_child].lazy_add += tree[idx_v].lazy_add;
      }

      tree[idx_v].lazy_add = 0;
    }
    if (tree[idx_v].reversed) {
      swap(tree[idx_v].idx_left_child, tree[idx_v].idx_right_child);
        if (tree[idx_v].idx_left_child != -1) tree[tree[idx_v].idx_left_child].reversed ^= 1;
        if (tree[idx_v].idx_right_child != -1) tree[tree[idx_v].idx_right_child].reversed ^= 1;
        tree[idx_v].reversed = 0;
    }
}

void update(int idx_v) {
  if (idx_v == -1) return;
  push(idx_v);
  int l = tree[idx_v].idx_left_child;
  int r = tree[idx_v].idx_right_child;

  tree[idx_v].count = 1 + get_cnt(l) + get_cnt(r);
  tree[idx_v].subtree_min = tree[idx_v].val;

  if (l != -1) {
      push(l);
      tree[idx_v].subtree_min = min(tree[idx_v].subtree_min, tree[l].subtree_min);
  }

  if (r != -1) {
      push(r);
      tree[idx_v].subtree_min = min(tree[idx_v].subtree_min, tree[r].subtree_min);
  }
}

void push_back(int val) {
    tree.emplace_back();
    Node& newNode = tree.back();
    newNode.val = val;
    newNode.subtree_min = 0;
    newNode.idx_left_child = -1;
    newNode.idx_right_child = -1;
    newNode.count = 1;
    newNode.priority = Gen();
    idx_root = merge(idx_root, tree.size() - 1);
}

  int merge(int idx_left_tree, int idx_right_tree) {
      if (idx_left_tree == -1) {
        if (idx_right_tree != -1) push(idx_right_tree);
        return idx_right_tree;
      }
      if (idx_right_tree == -1) {
        push(idx_left_tree);
        return idx_left_tree;
      }

      push(idx_left_tree);
      push(idx_right_tree);

      if (tree[idx_left_tree].priority < tree[idx_right_tree].priority) {
          tree[idx_right_tree].idx_left_child = merge(idx_left_tree, tree[idx_right_tree].idx_left_child);
          update(idx_right_tree);
          return idx_right_tree;
      } else {
          tree[idx_left_tree].idx_right_child = merge(tree[idx_left_tree].idx_right_child, idx_right_tree);
          update(idx_left_tree);
          return idx_left_tree;
      }
  }

  pair<int, int> split(int cur_idx, int split_key) {
      if (cur_idx == -1) return make_pair(-1, -1);

      push(cur_idx);
      update(cur_idx);
      int cur_key = get_cnt(tree[cur_idx].idx_left_child);

      if (split_key < cur_key) {
          auto [ll, lr] = split(tree[cur_idx].idx_left_child, split_key);
          tree[cur_idx].idx_left_child = lr;
          update(cur_idx);
          return make_pair(ll, cur_idx);
      } else {
          auto [rl, rr] = split(tree[cur_idx].idx_right_child, split_key - cur_key - 1);
          tree[cur_idx].idx_right_child = rl;
          update(cur_idx);
          return make_pair(cur_idx, rr);
      }
  }

  void reverse(int left_pos, int right_pos) {
      auto [l, mid_r] = split(idx_root, left_pos - 1);
      auto [mid, r] = split(mid_r, right_pos - left_pos);
      if (mid != -1) tree[mid].reversed ^= 1;
      idx_root = merge(l, merge(mid, r));
  }

  void add(int left_pos, int right_pos, int x) {
    auto [left, mid_r] = split(idx_root, left_pos - 1);
    auto [mid, right] =  split(mid_r, right_pos - left_pos);
    if (mid != -1) tree[mid].lazy_add += x;
    idx_root = merge(left, merge(mid, right));

  }
  void insert(int x,int p) {
    Treap::Node newNode;
    newNode.val = x;
    newNode.priority = Gen();
    newNode.count = 1;
    newNode.idx_left_child = -1;
    newNode.idx_right_child = -1;
    newNode.lazy_add = 0;
    newNode.subtree_min = x;
    tree.emplace_back(newNode);
    int new_idx = tree.size() - 1;
    auto [left, right] = split(idx_root, p);
    idx_root = merge(left, merge(new_idx, right));
}

void delet(int x) {
  auto [left, mid_right] = split(idx_root, x - 1);
  auto [mid, right] = split(mid_right, 0); 
  idx_root = merge(left, right);
}
void Min(int l, int r) {
  auto [left, mid_r] = split(idx_root, l - 1);
  auto [mid, right] = split(mid_r, r - l);
  if (mid != -1) cout << tree[mid].subtree_min << "\n";
  idx_root = merge(left,  merge(mid, right));
}
void revolve(int l,int r,int x){
  auto [left, mid_r] = split(idx_root, l - 1);
  auto [mid, right] = split(mid_r, r - l);
  if (mid != -1) {
    auto [ll,rr] = split(mid, r - l - x);
    idx_root = merge(left,  merge(rr, merge(ll,right)));
  }
}

  int Get(int key) {
      int cur = idx_root;
      while (true) {
          push(cur);
          int CurrentKey = get_cnt(tree[cur].idx_left_child);
          if (CurrentKey == key)
              return tree[cur].val;
          else if (CurrentKey > key)
              cur = tree[cur].idx_left_child;
          else {
              key -= (CurrentKey + 1);
              cur = tree[cur].idx_right_child;
          }
      }
  }

  int idx_root = -1;
  vector<Node> tree;
};

signed main() {
    ios::sync_with_stdio(0);
    cin.tie(0);
    int n, q;
    cin >> n ;
    Treap treap;
    for (int i = 0;i < n;i++) {
      int f;
      cin >> f;
      treap.push_back(f);
    }
    cin >> q;
    for (int i = 0; i < q; i++) {
      string t;
      cin >> t;
      if (t == "REVERSE"){
        int l,r;
        cin >> l >> r;
        l--,r--;
        treap.reverse(l,r);
      } else if (t == "INSERT"){
        int x, p;
        cin >> p >> x;
        p--;
        treap.insert(x,p);
      } else if (t == "REVOLVE"){
        long long l,r,x;
        cin >> l >> r >> x;
        l--,r--;
        x += (r - l + 1) * n;
        x %= (r - l + 1);
        treap.revolve(l,r,x);
      } else if (t == "DELETE"){
        int x;
        cin >> x;
        x--; 
        treap.delet(x);
      } else if (t == "MIN"){
        int l, r;
        cin >> l >> r;
        l--, r--;
        treap.Min(l,r);
      } else if (t == "ADD") {
        int x, y, d;
        cin >> x >> y >> d; 
        x--, y--;
        treap.add(x,y,d);
      }  
    }
}