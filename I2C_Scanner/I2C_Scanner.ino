/*
  ESP32 I2C Scanner
  功能：扫描I2C总线上连接的设备
  引脚：GPIO21 (SDA) 和 GPIO22 (SCL)
  扫描范围：0x08 至 0x77
  输出：在串口监视器中显示检测到的设备地址和总设备数量
*/

#include <Wire.h>  // 包含Wire库，用于I2C通信

// 定义I2C引脚
const int SDA_PIN = 21;  // GPIO21 作为SDA引脚
const int SCL_PIN = 22;  // GPIO22 作为SCL引脚

void setup() {
  // 初始化串口通信，波特率为115200
  Serial.begin(115200);
  
  // 等待串口初始化完成
  while (!Serial) {
    ; // 对于Leonardo/Micro/Zero等板卡，需要等待串口连接
  }
  
  // 打印开始信息
  Serial.println("====================================");
  Serial.println("ESP32 I2C 设备扫描器");
  Serial.println("====================================");
  
  // 初始化I2C通信，设置SDA和SCL引脚
  Wire.begin(SDA_PIN, SCL_PIN);
  
  // 打印初始化信息
  Serial.print("I2C通信已初始化，使用引脚：SDA = ");
  Serial.print(SDA_PIN);
  Serial.print(", SCL = ");
  Serial.println(SCL_PIN);
  Serial.println("开始扫描I2C设备...");
  Serial.println("------------------------------------");
}

void loop() {
  byte error, address;  // 用于存储错误状态和设备地址
  int deviceCount = 0;  // 设备计数器
  
  // 扫描0x08至0x77范围内的所有地址
  // 注意：I2C地址范围通常是0x08到0x77，0x00-0x07和0x78-0xFF是保留地址
  for (address = 0x08; address < 0x78; address++) {
    // 开始I2C传输到指定地址
    Wire.beginTransmission(address);
    
    // 结束传输并获取错误状态
    // 0表示成功，其他值表示错误
    error = Wire.endTransmission();
    
    // 检查是否成功连接到设备
    if (error == 0) {
      // 打印检测到的设备地址（十六进制格式）
      Serial.print("找到设备地址: 0x");
      if (address < 0x10) {
        Serial.print("0");  // 对于小于0x10的地址，添加前导零
      }
      Serial.println(address, HEX);
      deviceCount++;
    } else if (error == 4) {
      // 错误代码4表示未知错误
      Serial.print("在地址 0x");
      if (address < 0x10) {
        Serial.print("0");
      }
      Serial.println(address, HEX);
      Serial.println(" 发生未知错误");
    }
    // 其他错误代码：
    // 1: 数据发送超时
    // 2: 接收数据时收到NACK
    // 3: 发送数据时收到NACK
  }
  
  // 打印扫描结果
  Serial.println("------------------------------------");
  if (deviceCount == 0) {
    Serial.println("未检测到任何I2C设备");
  } else {
    Serial.print("扫描完成，共检测到 ");
    Serial.print(deviceCount);
    Serial.println(" 个I2C设备");
  }
  Serial.println("====================================");
  
  // 扫描完成后，延迟5秒再进行下一次扫描
  // 这样可以在串口监视器中更清晰地看到每次扫描的结果
  delay(5000);
}
