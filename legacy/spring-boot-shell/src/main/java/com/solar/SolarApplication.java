package com.solar;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.web.client.RestTemplate;

@SpringBootApplication
public class SolarApplication {

    public static void main(String[] args) {
        SpringApplication.run(SolarApplication.class, args);
    }

    // 注册 RestTemplate，这样你就可以在 Service 里注入它来调用 Python 了
    @Bean
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }
}